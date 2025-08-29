# TalentScout – Intelligent Hiring Assistant (Streamlit)

An intelligent screening chatbot for a fictional agency, **TalentScout**, that gathers candidate details and generates tailored technical questions from their declared tech stack. Built with **Streamlit** and a pluggable LLM backend.

## ✨ Features
- Friendly greeting, clear purpose, and conversation end via keywords (`quit`, `exit`, `bye`, `goodbye`, `stop`, `end`)
- Collects required info: full name, email, phone, years of experience, desired position(s), current location, tech stack
- Explicit consent before saving PII
- Tech-stack-driven question generation (3–5 per technology), scenario-focused
- Context-aware flow with fallbacks for unexpected inputs
- Sentiment analysis (VADER) to gauge tone; language auto-detect and reply in user language (via LLM prompt)
- Local JSONL storage (`data/candidates.json`) with opt-in only
- Clean Streamlit UI; modular codebase
- **Backends:** OpenAI (`gpt-4o-mini` by default) or a deterministic mock for local demos without keys

## 🧱 Repo Structure
```
talentscout_hiring_assistant/
├─ app.py
├─ llm.py
├─ prompts.py
├─ utils.py
├─ data/                 # local storage (JSONL)
├─ requirements.txt
└─ .env.example
```

## 🚀 Quickstart (Local)
1. **Clone / unzip** this project.
2. **Python 3.10+** recommended. Create a venv:
   ```bash
   python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
3. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment:
   - Copy `.env.example` to `.env`
   - Set `OPENAI_API_KEY=...`
   - Choose backend with `LLM_BACKEND=openai` or `mock`
   - Optionally set `OPENAI_MODEL=gpt-4o-mini`
5. Run Streamlit:
   ```bash
   streamlit run app.py
   ```

## 🧠 Prompt Design
- **System Prompt** sets role, scope, data collection fields, consent requirement, multilingual behavior, end-keyword handling, and safety/fallback expectations.
- **Info Collection Prompt** nudges stepwise acquisition of missing fields and confirmation loops.
- **Question Generation Prompt** requests JSON schema with 3–5 focused, scenario-based questions per tech item to keep UI predictable and parseable.
- **Fallback Message** provides actionable choices when input is unclear.

## 🔐 Data Privacy (GDPR-minded)
- **Consent first:** We only store to `data/candidates.json` if the user opts in.
- **Local only:** No external database is used in this demo.
- **Redaction:** The sidebar snapshot redacts the phone for casual viewing.
- **Right to withdraw:** Delete the JSONL line for your record locally if requested (IDs are shown after save).
- **Production note:** In real deployments, encrypt at rest, use role-based access, implement retention policies and audit logs, and publish a formal privacy policy & DPA.

## 🧪 Fallbacks & Context Handling
- Regex-based extraction for common fields (email/phone/experience).
- If the model returns non-JSON for question generation, the UI gracefully skips and continues the chat.
- Conversation is maintained in `st.session_state.messages`.

## 🌍 Multilingual
- The system prompt instructs the model to mirror the candidate’s language.
- `langdetect` infers user language for analytics; responses still rely on the LLM to adapt.

## 🧾 Optional Enhancements (ideas)
- **Sentiment dashboard:** Aggregate `sentiments` to flag frustration.
- **Fine-grained schemas:** Pydantic models for tech stacks by category (languages/frameworks/db/tools).
- **Multilingual translation:** Add a translation layer (e.g., NLLB) for non-English storage.
- **Cloud deploy:** Streamlit Community Cloud, AWS App Runner, GCP Cloud Run, or Azure App Service.
- **Authentication:** Add a recruiter login to review submissions.
- **Rate limits & caching:** Reduce cost/latency with response caching.

## 📹 Demo
- You can record a short Loom showcasing:
  1) Greeting & information gathering  
  2) Consent flow and save  
  3) Tech stack: _"Python, Django, PostgreSQL, Docker"_ → tailored questions  
  4) End with `quit`

## 🧰 Tech Stack
- **Frontend:** Streamlit
- **LLM:** OpenAI Chat Completions (pluggable); deterministic mock for testing
- **Utilities:** Pydantic, Email-Validator, VADER Sentiment, langdetect

## 📂 Simulated Data
- Saved as JSONL in `data/candidates.json` with `_id` and `_ts`.
- Example line:
  ```json
  {"full_name": "A B", "email": "a@b.com", "...": "...", "_id": "uuid", "_ts": 1724670000.0}
  ```

## 🧑‍💻 Development Notes
- Keep commit messages task-oriented (e.g., `feat: add consent gate`, `fix: robust phone parsing`).
- Type hints and docstrings are used across modules.

## ❓ Troubleshooting
- **No API key / offline:** set `LLM_BACKEND=mock` for a zero-cost demo.
- **Parsing errors:** Ensure the model returns the specified JSON schema; try lowering temperature.
- **Port conflicts:** `streamlit run app.py --server.port 8502`

---
© 2025 TalentScout . For academic use only.
--------
