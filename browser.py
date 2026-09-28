"""
browser.py - how the agent gets a browser.

Mode 1 (for forms that need Google sign-in):
    You run start_chrome.bat, which opens a normal Chrome window.
    You sign in to Google there yourself, once.
    The agent CONNECTS to that Chrome and opens the form in a new tab.
    Google sees a normal human sign-in, and the agent never touches your password.

Mode 2 (fallback, for forms that don't need sign-in):
    If that Chrome isn't running, the agent opens its own browser like before.
"""
from playwright.sync_api import Playwright, BrowserContext, Page

CHROME_DEBUG_URL = "http://localhost:9222"
FORM_READY = 'div[role="listitem"]'


class BrowserSession:
    def __init__(self, context: BrowserContext, connected: bool, browser=None):
        self.context = context
        self.connected = connected  # True = your own Chrome window
        self._browser = browser

    def close(self, page: Page) -> None:
        if self.connected:
            page.close()  # only close the agent's tab, leave your Chrome open
        else:
            self._browser.close()


def open_browser(p: Playwright) -> BrowserSession:
    try:
        browser = p.chromium.connect_over_cdp(CHROME_DEBUG_URL, timeout=3000)
        print("    Connected to your Chrome window (from start_chrome.bat).")
        return BrowserSession(browser.contexts[0], connected=True, browser=browser)
    except Exception:
        print("    Chrome from start_chrome.bat is not running - opening a separate browser.")
        print("    (Forms that need Google sign-in won't work in this mode.)")
        browser = p.chromium.launch(headless=False, slow_mo=100)
        return BrowserSession(browser.new_context(), connected=False, browser=browser)


def open_form(session: BrowserSession, url: str) -> Page:
    page = session.context.new_page()
    page.goto(url, wait_until="domcontentloaded")

    try:
        page.wait_for_selector(FORM_READY, timeout=10000)
    except Exception:
        if "accounts.google.com" in page.url:
            if not session.connected:
                raise SystemExit(
                    "\nThis form needs Google sign-in.\n"
                    "1. Close this, then double-click start_chrome.bat\n"
                    "2. Sign in to Google in the Chrome window that opens\n"
                    "3. Run the agent again - it will connect to that Chrome."
                )
            print("\n    Please sign in to Google in the Chrome window. The agent will wait...")
        else:
            print("\n    The form didn't load - check the browser window.")
            print("    ('You need permission' or 'form is closed' means it can't be filled.)")
        page.wait_for_selector(FORM_READY, timeout=0)  # wait as long as it takes

    page.wait_for_load_state("networkidle")
    return page
