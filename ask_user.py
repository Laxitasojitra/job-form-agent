"""
ask_user.py - asks the job seeker, in the terminal, for answers the agent
could not find itself. Shows numbered options, checks the answer, and
offers to remember it for future forms.
"""
import answer_memory
from llm_mapper import validate

FORMAT_HINTS = {
    "date": " (format YYYY-MM-DD, e.g. 2001-05-14)",
    "email": " (email address)",
    "number": " (number)",
    "url": " (full link, starting with https://)",
}


def parse_choice(field: dict, raw: str):
    """Turn what the user typed into a value. Options can be typed as numbers."""
    options = field["options"]
    if field["type"] == "checkbox":
        picks = [p.strip() for p in raw.split(",") if p.strip()]
        return [options[int(p) - 1] if p.isdigit() and 0 < int(p) <= len(options) else p
                for p in picks]
    if field["type"] in ("radio", "dropdown") and raw.isdigit() and 0 < int(raw) <= len(options):
        return options[int(raw) - 1]
    return raw


def ask_one(field: dict, reason: str, current=None):
    """Ask for one field. Returns the checked value, or None if the user skips."""
    print("\n" + "-" * 60)
    star = " *required*" if field["required"] else ""
    print(f"{field['label']}{star}")
    print(f"  (agent couldn't fill it: {reason})")
    if current is not None:
        print(f"  current value: {current}")

    if field["options"]:
        for i, opt in enumerate(field["options"], start=1):
            print(f"   {i}. {opt}")
        hint = " (numbers separated by commas)" if field["type"] == "checkbox" else " (number)"
    else:
        hint = FORMAT_HINTS.get(field["type"], "")

    while True:
        raw = input(f"  Your answer{hint}, or press Enter to skip: ").strip()
        if not raw:
            if field["required"]:
                print("  Skipped. Note: this is required, the form won't submit without it.")
            return None
        value, problem = validate(field, parse_choice(field, raw))
        if problem is None:
            return value
        print(f"  That doesn't fit ({problem}). Try again.")


def offer_to_remember(field: dict, value) -> None:
    if answer_memory.is_sensitive(field["label"]):
        print("  (Sensitive field - not saved, you'll be asked each time.)")
        return
    if input("  Remember this for future forms? (y/n): ").strip().lower() == "y":
        answer_memory.remember(field["label"], value)


def ask_missing(plan: list[dict]) -> None:
    """Ask the user for every field the agent couldn't fill. Required ones first."""
    missing = [item for item in plan
               if item["value"] is None and not item.get("asked")
               and item["field"]["type"] != "unknown"]
    if not missing:
        return

    missing.sort(key=lambda item: not item["field"]["required"])
    print(f"\nI need your help with {len(missing)} field(s).")
    for item in missing:
        value = ask_one(item["field"], item["problem"])
        if value is not None:
            item.update(value=value, source="you", problem=None)
            offer_to_remember(item["field"], value)
