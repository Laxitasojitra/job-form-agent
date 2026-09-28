"""
list_models.py - shows which models your API key can use,
and which model the agent is set to use right now.

Run:  python list_models.py
"""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key=os.getenv("LLM_API_KEY"))

print("Agent is set to use :", os.getenv("LLM_MODEL"))
print("Backup model        :", os.getenv("LLM_FALLBACK_MODEL") or "(none)")
print("\nModels available to your key:")

for model in sorted(client.models.list(), key=lambda m: m.id):
    name = model.id.removeprefix("models/")
    marker = "  <-- agent uses this" if name == os.getenv("LLM_MODEL") else ""
    print("  ", name + marker)
