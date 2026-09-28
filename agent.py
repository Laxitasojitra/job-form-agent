"""
agent.py - the full agent.

For every page of the form:
  1. Read the questions
  2. Find answers: profile (+ resume), then the agent searches resume, past answers, derivations
  3. Written questions ("Why join us?"): asks YOU whether AI should draft it, you type it, or skip
  4. Ask YOU for any other missing fields
  5. Fill the page, then review: see every answer and its source, change anything
  6. You click Next in the browser -> the agent fills the next page automatically

It NEVER clicks Next or Submit - you do.

Run:  python agent.py <google_form_url>
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Locator

from answer_memory import is_sensitive
from ask_user import ask_missing, ask_one, offer_to_remember
from browser import open_browser, open_form
from form_reader import read_google_form
from llm_mapper import build_plan
from resume_reader import load_profile
from writer import handle_written, write_one

SOURCE_LABELS = {
    "profile": "profile",
    "written": "AI draft, approved by you",
    "resume": "found in resume",
    "memory": "your earlier answer",
    "derived": "worked out by agent",
    "you": "typed by you",
}


# ---------------------------------------------------------------- filling
def question_box(page: Page, field_id: str) -> Locator:
    """Field ids are 'q<index>', matching the question's position in the form."""
    return page.locator('div[role="listitem"]').nth(int(field_id[1:]))


def option_label(opt: Locator) -> str:
    label = (opt.get_attribute("data-value") or opt.get_attribute("data-answer-value")
             or opt.get_attribute("aria-label") or "")
    return " ".join(label.split())


def click_option(options: Locator, value: str) -> bool:
    for opt in options.all():
        if option_label(opt) == value:
            opt.click()
            return True
    return False


def fill_field(page: Page, field: dict, value) -> None:
    q = question_box(page, field["id"])
    ftype = field["type"]

    if ftype == "long_text":
        q.locator("textarea").first.fill(value)
    elif ftype == "radio":
        if not click_option(q.locator('div[role="radio"]'), value):
            raise ValueError("option not found on page")
    elif ftype == "checkbox":
        # Tick wanted boxes AND untick unwanted ones (matters when you edit an answer)
        for opt in q.locator('div[role="checkbox"]').all():
            wanted = option_label(opt) in value
            ticked = opt.get_attribute("aria-checked") == "true"
            if wanted != ticked:
                opt.click()
    elif ftype == "dropdown":
        q.locator('div[role="listbox"]').first.click()
        page.wait_for_timeout(500)
        if not click_option(q.locator('div[role="option"]'), value):
            page.keyboard.press("Escape")
            raise ValueError("option not found on page")
        page.wait_for_timeout(300)
    else:  # text, email, date, number, url...
        q.locator('input:not([type="hidden"])').first.fill(str(value))


def fill_all(page: Page, plan: list[dict]) -> None:
    for item in plan:
        if item["value"] is None:
            continue
        try:
            fill_field(page, item["field"], item["value"])
            item["filled"] = True
        except Exception as e:
            item["filled"] = False
            item["problem"] = f"could not fill on page ({e})"


# ---------------------------------------------------------------- review
def print_review(plan: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("REVIEW - check every answer here AND in the browser")
    print("=" * 70)
    for n, item in enumerate(plan, start=1):
        label = item["field"]["label"]
        if item.get("filled"):
            print(f"{n:>2}. [OK]     {label}")
            print(f"              -> {item['value']}   ({SOURCE_LABELS.get(item['source'], item['source'])})")
        else:
            req = "  *REQUIRED*" if item["field"]["required"] else ""
            print(f"{n:>2}. [EMPTY]  {label}{req}")
            print(f"              -> {item['problem']}")
    print("=" * 70)


def review_loop(page: Page, plan: list[dict], ctx: dict) -> None:
    """Let the user change any answer on this page before moving on."""
    while True:
        print_review(plan)
        choice = input(
            "\nType a number to change that answer, or press Enter when this page looks right: "
        ).strip()
        if not choice:
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(plan):
            print("Please type a number from the list.")
            continue

        item = plan[int(choice) - 1]
        if item["field"]["type"] == "unknown":
            print("The agent can't fill this question type yet - please fill it in the browser.")
            continue

        if item.get("needs_writing"):
            write_one(item, ctx["form_title"], ctx["profile"], ctx["resume_text"])
        else:
            value = ask_one(item["field"], "you chose to change it", current=item["value"])
            if value is None:
                continue
            item.update(value=value, source="you", problem=None)
            offer_to_remember(item["field"], value)

        if item["value"] is None:
            continue
        try:
            fill_field(page, item["field"], item["value"])
            item["filled"] = True
        except Exception as e:
            item["filled"] = False
            item["problem"] = f"could not fill on page ({e})"


# ---------------------------------------------------------------- pages
def page_signature(page: Page) -> tuple:
    """The list of question titles on screen - changes when the user goes to another page."""
    try:
        headings = page.locator('div[role="listitem"] div[role="heading"]').all_inner_texts()
        return tuple(" ".join(h.split()) for h in headings)
    except Exception:
        return ()  # page is in the middle of loading


def next_button_text(page: Page) -> str:
    for name in ("Submit", "Next"):
        if page.get_by_role("button", name=name, exact=True).count():
            return name
    return ""


def wait_for_next_page(page: Page, current: tuple) -> str:
    """Wait while the user clicks Next/Back/Submit in the browser.
    Returns 'new_page' or 'finished'."""
    empty_checks = 0
    while True:
        if page.is_closed():
            return "finished"
        page.wait_for_timeout(1000)
        sig = page_signature(page)
        if not sig:
            empty_checks += 1
            if empty_checks >= 3:  # no questions for 3 seconds = confirmation page
                return "finished"
            continue
        empty_checks = 0
        if sig != current:
            page.wait_for_load_state("networkidle")
            return "new_page"


def process_page(page: Page, page_no: int, ctx: dict) -> list[dict]:
    print(f"\n######## PAGE {page_no} ########")
    print("Reading the questions...")
    fields = read_google_form(page)
    print(f"    Found {len(fields)} questions.")

    print("Finding answers...")
    plan = build_plan(fields, ctx["profile"], ctx["resume_text"])

    handle_written(plan, ctx["form_title"], ctx["profile"], ctx["resume_text"])
    ask_missing(plan)

    print("\nFilling this page...")
    fill_all(page, plan)
    review_loop(page, plan, ctx)
    return plan


def save_log(all_plans: list[dict]) -> None:
    Path("output").mkdir(exist_ok=True)
    log = [{**item, "value": "***hidden***"} if is_sensitive(item["field"]["label"]) else item
           for item in all_plans]  # never write Aadhaar, bank details etc. to disk
    Path("output/last_run.json").write_text(
        json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------- main
def main():
    url = sys.argv[1] if len(sys.argv) > 1 else input("Paste Google Form URL: ").strip()

    print("Loading your profile...")
    profile, resume_text = load_profile()

    with sync_playwright() as p:
        session = open_browser(p)
        page = open_form(session, url)
        ctx = {"profile": profile, "resume_text": resume_text, "form_title": page.title()}

        all_plans, seen_pages, page_no = [], set(), 0
        while True:
            sig = page_signature(page)
            if sig in seen_pages:
                print("\nThis page was already filled earlier - your answers are still there, "
                      "so the agent won't refill it.")
            else:
                page_no += 1
                seen_pages.add(sig)
                all_plans += process_page(page, page_no, ctx)
                save_log(all_plans)

            button = next_button_text(page)
            if button == "Next":
                print("\n>> Check this page in the browser, then click NEXT there. "
                      "The agent will fill the next page automatically.")
            else:
                print("\n>> This looks like the last page. Check everything in the browser, "
                      "then click SUBMIT yourself.")
            print("   (If Next doesn't work, a required field is empty - fill it in the browser.)")

            if wait_for_next_page(page, sig) == "finished":
                break

        print("\nForm finished. The agent never clicked Submit - you did. Good luck!")
        if not page.is_closed():
            session.close(page)


if __name__ == "__main__":
    main()
