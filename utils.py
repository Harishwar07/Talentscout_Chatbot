# utils.py
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

END_KEYWORDS = {"bye", "exit", "quit", "stop", "end", "thank you", "thanks"}

def is_end_message(s: str) -> bool:
    s = (s or "").strip().lower()
    return s in END_KEYWORDS

def anonymize(value: str) -> str:
    """
    Very simple anonymizer: keeps first letter of each token and replaces the rest.
    Email/phone masking should be handled by specific helpers if needed.
    """
    if not value:
        return value
    parts = re.split(r"(\W+)", value)
    out = []
    for p in parts:
        if p.isalpha() and len(p) > 1:
            out.append(p[0] + "*" * (len(p) - 1))
        elif re.fullmatch(r"\d{3,}", p or ""):
            out.append("*" * len(p))
        else:
            out.append(p)
    return "".join(out)

def mask_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return anonymize(email)
    user, domain = email.split("@", 1)
    if not user:
        return anonymize(email)
    masked_user = user[0] + "*" * max(1, len(user) - 1)
    return f"{masked_user}@{domain}"

def safe_extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first JSON object from text. Returns dict or None.
    """
    if not text:
        return None
    # try direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # try to locate first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None

def tech_list_from_input(s: str) -> List[str]:
    items = [t.strip() for t in (s or "").split(",")]
    # filter out empties and clearly irrelevant tokens
    items = [t for t in items if t and re.search(r"[a-zA-Z]", t)]
    # normalize basic casing
    return [t[:50] for t in items][:10]  # cap length and count for safety

def parse_1_to_10(s: str) -> Optional[int]:
    m = re.search(r"\b([1-9]|10)\b", (s or "").strip())
    if not m:
        return None
    return int(m.group(1))

def pretty_summary(candidate: Dict[str, Any]) -> str:
    lines = []
    for k, v in candidate.items():
        lines.append(f"- **{k}**: {v}")
    return "\n".join(lines)

def save_simulated(snapshot: Dict[str, Any], path: str = "candidates.jsonl") -> str:
    """
    Save anonymized/simulated snapshot as a JSONL line. Returns path.
    """
    record = {
        "ts": datetime.utcnow().isoformat() + "Z",
        **snapshot,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
