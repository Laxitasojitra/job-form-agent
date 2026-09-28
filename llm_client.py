"""
llm_client.py - one place that talks to the LLM.
Every part of the agent (resume reading, form mapping, self-search) uses llm_json(),
so they all get retries, the backup model, and JSON clean-up for free.
"""
import json
import os
import re
import time

from dotenv import load_dotenv
from openai import (
    OpenAI, RateLimitError, InternalServerError, APIConnectionError, APITimeoutError,
    BadRequestError,
)

load_dotenv()

# Errors that usually go away if we wait and try again:
# 429 = rate limit, 5xx = server busy, connection problems
TEMPORARY_ERRORS = (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError)
WAIT_SECONDS = [5, 15, 30, 60]


def get_providers() -> list[dict]:
    """Main LLM from LLM_*, optional backup from LLM_FALLBACK_*.
    The backup can be a different model on the same service, or a different service."""
    main = {
        "base_url": os.getenv("LLM_BASE_URL"),
        "api_key": os.getenv("LLM_API_KEY"),
        "model": os.getenv("LLM_MODEL"),
    }
    if not all(main.values()) or main["api_key"].startswith("paste_"):
        raise SystemExit("LLM settings missing. Copy .env.example to .env and fill it in.")

    providers = [main]
    if os.getenv("LLM_FALLBACK_MODEL"):
        providers.append({
            "base_url": os.getenv("LLM_FALLBACK_BASE_URL") or main["base_url"],
            "api_key": os.getenv("LLM_FALLBACK_API_KEY") or main["api_key"],
            "model": os.getenv("LLM_FALLBACK_MODEL"),
        })
    return providers


def extract_json(text: str) -> dict:
    """Clean up common LLM output problems before parsing:
    <think>...</think> blocks from reasoning models, ```json fences, extra text around the JSON."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in the reply")
    return json.loads(text[start:end + 1])


def _call(client: OpenAI, model: str, messages: list[dict]) -> dict:
    try:
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=0.2,
            response_format={"type": "json_object"},  # ask for pure JSON
        )
    except BadRequestError:
        # Some models don't support JSON mode - ask again without it
        response = client.chat.completions.create(
            model=model, messages=messages, temperature=0.2,
        )
    return extract_json(response.choices[0].message.content)


def llm_json(system_prompt: str, user_message: str) -> dict:
    """Send a prompt, get back a parsed JSON dict. Retries, then tries the backup model."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    for p in get_providers():
        # Long timeout: local models on a laptop CPU can take a few minutes
        client = OpenAI(base_url=p["base_url"], api_key=p["api_key"], timeout=300)
        for attempt, wait in enumerate([0] + WAIT_SECONDS, start=1):
            if wait:
                print(f"    Waiting {wait}s, then retrying ({attempt}/{len(WAIT_SECONDS) + 1})...")
                time.sleep(wait)
            try:
                return _call(client, p["model"], messages)
            except TEMPORARY_ERRORS as e:
                print(f"    {p['model']}: {type(e).__name__}")
            except (ValueError, json.JSONDecodeError) as e:
                print(f"    {p['model']} gave a broken reply ({e})")
        print(f"    {p['model']} failed, trying the next option.")

    raise SystemExit("No LLM is responding right now. Check .env or try again later.")
