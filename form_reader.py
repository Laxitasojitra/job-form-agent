"""
form_reader.py - Phase 2
Opens a Google Form and extracts every question: label, type, options, required.
Output is printed and saved to output/fields.json.

Run:  python form_reader.py <google_form_url>
      (or just run it in PyCharm and paste the URL when asked)
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, Locator


def clean(text: str | None) -> str:
    """Collapse extra spaces and newlines."""
    return " ".join((text or "").split())


def read_dropdown_options(page: Page, question: Locator) -> list[str]:
    """Google Form dropdowns only show options after clicking, so open, read, close."""
    question.locator('div[role="listbox"]').first.click()
    page.wait_for_timeout(500)

    values = []
    for option in question.locator('div[role="option"]').all():
        value = clean(option.get_attribute("data-value"))
        if value and value not in values:  # skip the empty "Choose" option
            values.append(value)

    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return values


def read_google_form(page: Page) -> list[dict]:
    fields = []
    questions = page.locator('div[role="listitem"]')

    for i in range(questions.count()):
        q = questions.nth(i)
        heading = q.locator('div[role="heading"]')
        if heading.count() == 0:
            continue  # section title or image block, not a question

        title = clean(heading.first.inner_text())
        field = {
            "id": f"q{i}",
            "label": title.rstrip("* ").strip(),
            "required": title.endswith("*"),
            "type": "unknown",
            "options": [],
        }

        radios = q.locator('div[role="radio"]')
        checkboxes = q.locator('div[role="checkbox"]')
        inputs = q.locator('input:not([type="hidden"])')

        if radios.count():
            field["type"] = "radio"
            field["options"] = [
                clean(r.get_attribute("data-value") or r.get_attribute("aria-label"))
                for r in radios.all()
            ]
        elif checkboxes.count():
            field["type"] = "checkbox"
            field["options"] = [
                clean(c.get_attribute("data-answer-value") or c.get_attribute("aria-label"))
                for c in checkboxes.all()
            ]
        elif q.locator('div[role="listbox"]').count():
            field["type"] = "dropdown"
            field["options"] = read_dropdown_options(page, q)
        elif q.locator("textarea").count():
            field["type"] = "long_text"
        elif inputs.count():
            input_type = inputs.first.get_attribute("type") or "text"
            field["type"] = input_type  # text, email, date, number, url...

        fields.append(field)

    return fields


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else input("Paste Google Form URL: ").strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)  # visible, so you can watch
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector('div[role="listitem"]', timeout=15000)

        fields = read_google_form(page)

        print(json.dumps(fields, indent=2, ensure_ascii=False))
        print(f"\nFound {len(fields)} questions.")

        Path("output").mkdir(exist_ok=True)
        Path("output/fields.json").write_text(
            json.dumps(fields, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("Saved to output/fields.json")

        input("\nPress Enter to close the browser...")
        browser.close()


if __name__ == "__main__":
    main()
