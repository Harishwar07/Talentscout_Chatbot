# app.py
import os
import time
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, Any, List, Optional
from utils import (
    anonymize,
    mask_email,
    safe_extract_json,
    is_end_message,
    pretty_summary,
    tech_list_from_input,
    parse_1_to_10,
    save_simulated,
)

# ---------- Config ----------
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    st.error("Please set GEMINI_API_KEY in a .env file (Google AI Studio API key).")
    st.stop()

genai.configure(api_key=API_KEY)
MODEL_NAME = os.getenv("PREFERRED_GEMINI_MODEL", "gemini-1.5-flash")

try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception:
    model = None

def safe_generate(prompt: str, retries: int = 3, backoff: float = 1.0) -> str:
    last_exc = None
    for i in range(retries):
        try:
            if model is not None:
                resp = model.generate_content(prompt)
                if hasattr(resp, "text"):
                    return resp.text
                if hasattr(resp, "content"):
                    return resp.content
                return str(resp)
            else:
                # Fallback path if SDK variant differs
                res = genai.generate_text(model=MODEL_NAME, input=prompt)
                if hasattr(res, "text"):
                    return res.text
                if getattr(res, "candidates", None):
                    c = res.candidates[0]
                    return getattr(c, "content", getattr(c, "text", str(c)))
                return str(res)
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (2 ** i))
    raise RuntimeError(f"LLM request failed: {last_exc}")

# ---------- LLM helpers (questions & summary) ----------
def llm_generate_questions(techs: List[str]) -> Dict[str, List[str]]:
    """
    Ask Gemini to return 3–5 concise practical questions for each tech as pure JSON.
    """
    tech_list_str = ", ".join(techs)
    prompt = f"""
Generate interview questions for the following technologies: {tech_list_str}.
Return ONLY JSON like:
{{
  "Python": ["Q1", "Q2", "Q3"],
  "Django": ["Q1", "Q2", "Q3"]
}}
- 3 to 5 practical questions per technology
- Keep questions clear and concise.
No extra text besides JSON.
"""
    raw = safe_generate(prompt, retries=3)
    data = safe_extract_json(raw) or {}
    # sanitize: ensure lists & 3-5 boundaries
    cleaned: Dict[str, List[str]] = {}
    for t in techs:
        qs = data.get(t) or data.get(t.capitalize()) or data.get(t.lower()) or []
        if isinstance(qs, list):
            qs = [str(q).strip() for q in qs if str(q).strip()]
            if len(qs) < 3:  # fallback if LLM under-returns
                qs += [f"Briefly explain a key concept in {t}.",
                       f"How do you debug common issues in {t}?",
                       f"Describe a challenging {t} task you solved."]
            cleaned[t] = qs[:5]
    return cleaned

def llm_score_answer(question: str, answer: str) -> Dict[str, Any]:
    """
    Get a simple 1–10 score + short feedback for one answer.
    """
    prompt = f"""
Rate the following interview answer from 1 to 10 (higher is better).
Return ONLY JSON: {{"score": <int 1-10>, "feedback": "short constructive feedback"}}

Question: {question}
Answer: {answer}
"""
    raw = safe_generate(prompt, retries=2)
    data = safe_extract_json(raw) or {}
    score = data.get("score")
    feedback = data.get("feedback")
    try:
        score = int(score) if score is not None else None
    except Exception:
        score = None
    return {"score": score, "feedback": feedback}

def llm_final_summary(candidate_info: Dict[str, Any]) -> str:
    """
    Ask LLM to summarize strengths/weaknesses/fit based on collected info,
    self-ratings, and answers with scores.
    """
    info = candidate_info.get("info", {})
    ratings = candidate_info.get("ratings", {})
    answers = candidate_info.get("answers", [])
    prompt = f"""
You are an interview assistant. Summarize the candidate in 130-180 words:
- Strengths
- Weaknesses
- Overall fit for the role

Context:
Info: {info}
Self-ratings: {ratings}
Answers & scores: {answers}

Return a concise, readable paragraph (no JSON).
"""
    return safe_generate(prompt, retries=2).strip()

# ---------- Session State ----------
if "history" not in st.session_state:
    st.session_state.history: List[Dict[str, str]] = []
if "step" not in st.session_state:
    st.session_state.step = "greet"  # greet -> fields -> ratings -> tech_q -> summary -> done
if "field_index" not in st.session_state:
    st.session_state.field_index = 0
if "candidate" not in st.session_state:
    st.session_state.candidate = {
        "Full Name": None,
        "Email Address": None,
        "Phone Number": None,
        "Years of Experience": None,
        "Desired Position(s)": None,
        "Current Location": None,
        "Tech Stack": None,
    }
if "techs" not in st.session_state:
    st.session_state.techs: List[str] = []
if "ratings" not in st.session_state:
    st.session_state.ratings: Dict[str, int] = {}
if "qmap" not in st.session_state:
    st.session_state.qmap: Dict[str, List[str]] = {}
if "flat_questions" not in st.session_state:
    st.session_state.flat_questions: List[Dict[str, Any]] = []
if "q_ptr" not in st.session_state:
    st.session_state.q_ptr = 0
if "answers" not in st.session_state:
    st.session_state.answers: List[Dict[str, Any]] = []
if "consent" not in st.session_state:
    st.session_state.consent = False

FIELDS = [
    "Full Name",
    "Email Address",
    "Phone Number",
    "Years of Experience",
    "Desired Position(s)",
    "Current Location",
    "Tech Stack",
]

# ---------- UI ----------
st.set_page_config(page_title="TalentScout — LLM Hiring Assistant", page_icon="🤝")
st.title("🤝 TalentScout — LLM Hiring Assistant")

with st.expander("🔐 Privacy & Data Handling (GDPR-style notice)", expanded=True):
    st.markdown(
        "- We collect only interview-related details.\n"
        "- Any stored data is **anonymized/simulated** (no raw email/phone).\n"
        "- Data is saved locally to `candidates.jsonl` **only if you consent**.\n"
        "- Click **Erase session data** below to clear this session."
    )
    st.checkbox("I consent to store anonymized data for demo purposes.", key="consent")

col_a, col_b = st.columns(2)
with col_a:
    if st.button("🧹 Erase session data"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
with col_b:
    st.caption("Erases only in-memory session; saved JSONL isn’t altered.")

# Show chat history
for m in st.session_state.history:
    st.chat_message(m["role"]).markdown(m["text"])

def say(text: str, role: str = "assistant"):
    st.chat_message(role).markdown(text)
    st.session_state.history.append({"role": role, "text": text})

# ---------- Conversation Flow (Deterministic; LLM only for content) ----------
def ask_next_field():
    i = st.session_state.field_index
    if i >= len(FIELDS):
        return
    field = FIELDS[i]
    prompts = {
        "Full Name": "What is your **Full Name**?",
        "Email Address": "Please share your **Email Address**.",
        "Phone Number": "What is your **Phone Number**?",
        "Years of Experience": "How many **Years of Experience** do you have?",
        "Desired Position(s)": "What is/are your **Desired Position(s)**?",
        "Current Location": "Where are you currently located?",
        "Tech Stack": "Please list your **Tech Stack** (comma-separated, e.g., Python, Django, React).",
    }
    say(prompts[field])

def validate_and_store(field: str, user_text: str) -> Optional[str]:
    u = (user_text or "").strip()
    # polite re-ask messages
    if field == "Full Name":
        if len(u.split()) < 2:
            return "Please enter your **first and last name**."
        st.session_state.candidate[field] = anonymize(u)  # store anonymized display version
    elif field == "Email Address":
        if "@" not in u or "." not in u:
            return "That doesn’t look like a valid email. Please re-enter your **Email Address**."
        st.session_state.candidate[field] = mask_email(u)
    elif field == "Phone Number":
        digits = "".join(ch for ch in u if ch.isdigit())
        if not (7 <= len(digits) <= 15):
            return "Please enter a valid **Phone Number** (7–15 digits)."
        st.session_state.candidate[field] = anonymize(u)
    elif field == "Years of Experience":
        if not u.isdigit():
            return "Please enter your experience in **numbers only** (e.g., 3)."
        st.session_state.candidate[field] = u
    elif field == "Desired Position(s)":
        if len(u) < 2:
            return "That seems too short. Please provide your **Desired Position(s)**."
        st.session_state.candidate[field] = u
    elif field == "Current Location":
        if len(u) < 2:
            return "Please provide a valid **Current Location** (city/region)."
        st.session_state.candidate[field] = u
    elif field == "Tech Stack":
        techs = tech_list_from_input(u)
        if not techs:
            return "I couldn’t understand your tech stack. Please list technologies **comma-separated** (e.g., Python, Django)."
        st.session_state.candidate[field] = ", ".join(techs)
        st.session_state.techs = techs
    return None

def ensure_greeting_once():
    if not st.session_state.history:
        say("Hello! I'm your AI hiring assistant. Let’s get started with your details.")

# Initial greet + first field
if st.session_state.step == "greet":
    ensure_greeting_once()
    st.session_state.step = "fields"
    st.session_state.field_index = 0
    ask_next_field()

user_input = st.chat_input("Type here…")
if user_input:
    # End early if needed
    if is_end_message(user_input):
        say("Thank you for your time! Our team will reach out soon. 👋")
        # Save anonymized snapshot if consented
        if st.session_state.consent:
            snapshot = {
                "info": st.session_state.candidate,
                "ratings": st.session_state.ratings,
                "answers": st.session_state.answers,
                "summary": None,
            }
            save_simulated(snapshot)
        st.stop()

    st.chat_message("user").markdown(user_input)
    st.session_state.history.append({"role": "user", "text": user_input})

    # Step: collect fields
    if st.session_state.step == "fields":
        current_field = FIELDS[st.session_state.field_index]
        err = validate_and_store(current_field, user_input)
        if err:
            say(err)
        else:
            st.session_state.field_index += 1
            if st.session_state.field_index < len(FIELDS):
                ask_next_field()
            else:
                # Move to ratings
                st.session_state.step = "ratings"
                st.session_state.rating_idx = 0
                techs = st.session_state.techs
                if techs:
                    say("Before technical questions, please rate your confidence for each tech (1–10).")
                    say(f"On a scale of 1–10, how confident are you in **{techs[0]}**?")
                else:
                    # Should not happen because Tech Stack is required
                    say("Let’s move to technical questions.")
                    st.session_state.step = "tech_q"
                    st.session_state.q_ptr = 0

    # Step: self-ratings per tech
    elif st.session_state.step == "ratings":
        techs = st.session_state.techs
        idx = st.session_state.get("rating_idx", 0)
        if 0 <= idx < len(techs):
            val = parse_1_to_10(user_input)
            if val is None:
                say("Please enter a number **1–10**.")
            else:
                st.session_state.ratings[techs[idx]] = val
                idx += 1
                st.session_state.rating_idx = idx
                if idx < len(techs):
                    say(f"Thanks. On a scale of 1–10, how confident are you in **{techs[idx]}**?")
                else:
                    # Generate questions via LLM
                    say("Great. Generating technical questions…")
                    qmap = llm_generate_questions(techs)
                    st.session_state.qmap = qmap
                    # Flatten to a list of dicts: [{"tech":...,"q":...}, ...]
                    flat: List[Dict[str, Any]] = []
                    for t in techs:
                        for q in qmap.get(t, []):
                            flat.append({"tech": t, "q": q})
                    st.session_state.flat_questions = flat
                    st.session_state.q_ptr = 0
                    st.session_state.step = "tech_q"
                    if flat:
                        first = flat[0]
                        say(f"**{first['tech']} Q1:** {first['q']}")
                    else:
                        say("I couldn't generate questions right now. Please re-enter your **Tech Stack**.")
                        st.session_state.step = "fields"
                        st.session_state.field_index = FIELDS.index("Tech Stack")

    # Step: ask/collect technical answers one-by-one (with LLM scoring)
    elif st.session_state.step == "tech_q":
        ptr = st.session_state.q_ptr
        flat = st.session_state.flat_questions
        if 0 <= ptr < len(flat):
            current = flat[ptr]
            qtext = current["q"]
            tech = current["tech"]
            ans = user_input.strip()
            # score via LLM (non-blocking feel; still simple call)
            try:
                score_pack = llm_score_answer(qtext, ans)
            except Exception:
                score_pack = {"score": None, "feedback": None}
            st.session_state.answers.append({
                "tech": tech,
                "question": qtext,
                "answer": ans,
                "score": score_pack.get("score"),
                "feedback": score_pack.get("feedback"),
            })
            # next question or finish
            ptr += 1
            st.session_state.q_ptr = ptr
            if ptr < len(flat):
                next_q = flat[ptr]
                # compute number per tech for label
                count_for_tech = 1 + sum(1 for i in range(ptr) if flat[i]["tech"] == next_q["tech"])
                say(f"**{next_q['tech']} Q{count_for_tech}:** {next_q['q']}")
            else:
                # summary
                st.session_state.step = "summary"
                say("Thanks! Preparing a brief summary…")
                # Build a compact object for summary
                summary_context = {
                    "info": st.session_state.candidate,
                    "ratings": st.session_state.ratings,
                    "answers": st.session_state.answers,
                }
                try:
                    final = llm_final_summary(summary_context)
                except Exception:
                    final = "Summary unavailable due to a temporary issue."
                st.session_state.final_summary = final
                say(final)
                say("Thank you for your time! Our team will reach out soon. 👋")
                # Save anonymized snapshot if consented
                if st.session_state.consent:
                    snapshot = {
                        "info": st.session_state.candidate,
                        "ratings": st.session_state.ratings,
                        "answers": st.session_state.answers,
                        "summary": final,
                    }
                    save_simulated(snapshot)
                st.session_state.step = "done"

    elif st.session_state.step == "summary":
        # If user chats after summary, just acknowledge and end.
        say("Thanks again! You may close this window. 👋")

    elif st.session_state.step == "done":
        say("Session completed. Type 'exit' to close.")
