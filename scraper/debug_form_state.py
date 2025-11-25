"""Debug script to inspect form state after filling."""

from playwright.sync_api import sync_playwright
from scraper.portal_interactions import click_advanced_filter, fill_search_form
from scraper.portal_selectors import PORTAL_URL
from datetime import datetime
import time

def debug_form():
    """Open browser, fill form, and pause for manual inspection."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Navigating to portal...")
        page.goto(PORTAL_URL, wait_until='networkidle')

        print("Clicking Advanced...")
        click_advanced_filter(page)

        print("Filling form...")
        fill_search_form(
            page,
            county_name="Wake County",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            search_text="24SP*"
        )

        print("\n" + "="*60)
        print("FORM FILLED - BROWSER PAUSED FOR INSPECTION")
        print("="*60)
        print("\nPlease check:")
        print("1. Is 'Wake County' selected in Court Location dropdown?")
        print("2. Is 'Pending' selected in Case Status dropdown?")
        print("3. Is 'Special Proceedings' selected in Case Type dropdown?")
        print("4. Are the dates filled correctly?")
        print("5. Is the search text '24SP*' present?")
        print("\nPress Ctrl+C when done inspecting...")
        print("="*60 + "\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nClosing browser...")
            browser.close()

if __name__ == '__main__':
    debug_form()
