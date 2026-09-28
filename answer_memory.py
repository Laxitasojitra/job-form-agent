"""
answer_memory.py - remembers answers you typed yourself, so the agent
can find them on its own next time (in any company's form).

Stored in answers.json on your laptop only (it's in .gitignore).
Sensitive fields (Aadhaar, PAN, bank details, passwords...) are NEVER stored.
"""
import json
import re
from pathlib import Path

MEMORY_FILE = Path("answers.json")

# Fields the agent must never fill automatically, send to the LLM as values, or remember
SENSITIVE_WORDS = [
    "aadhaar", "aadhar", "pan card", "pan number", "passport", "voter id",
    "bank", "account number", "ifsc", "upi", "card number", "cvv",
    "password", "otp", "atm pin", "ssn", "social security",
]


def is_sensitive(label: str) -> bool:
    text = label.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in SENSITIVE_WORDS)


def normalize(label: str) -> str:
    """'Your Email Address *' and 'email address' should match the same memory."""
    words = re.sub(r"[^a-z0-9 ]", " ", label.lower()).split()
    stop = {"your", "the", "a", "an", "please", "enter", "select", "provide", "of", "in", "and"}
    return " ".join(w for w in words if w not in stop)


def load() -> dict:
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    return {}


def recall(label: str):
    """Exact match on the normalized question. Returns the saved value or None."""
    entry = load().get(normalize(label))
    return entry["value"] if entry else None


def remember(label: str, value) -> None:
    if is_sensitive(label):
        return  # never store sensitive data
    memory = load()
    memory[normalize(label)] = {"label": label, "value": value}
    MEMORY_FILE.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def all_answers() -> list[dict]:
    """Everything remembered, as a list the LLM can search through."""
    return [{"question": e["label"], "answer": e["value"]} for e in load().values()]
