"""Debug script to inspect and print actual form values."""

from playwright.sync_api import sync_playwright
from scraper.portal_interactions import click_advanced_filter, fill_search_form
from scraper.portal_selectors import PORTAL_URL
from datetime import datetime
import time

def debug_form_values():
    """Open browser, fill form, print actual values, and pause."""
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
        print("FORM FILLED - EXTRACTING ACTUAL VALUES")
        print("="*60 + "\n")

        # Get search criteria value
        search_val = page.input_value('#caseCriteria_SearchCriteria')
        print(f"Search Criteria: {search_val}")

        # Get date values
        start_date = page.input_value('#caseCriteria\\.FileDateStart')
        end_date = page.input_value('#caseCriteria\\.FileDateEnd')
        print(f"File Date Start: {start_date}")
        print(f"File Date End: {end_date}")

        # Get Court Location dropdown selected text
        try:
            court_location = page.evaluate('''
                () => {
                    const dropdown = document.querySelector("#caseCriteria_CourtLocation");
                    if (dropdown) {
                        const kendoDropDown = $(dropdown).data("kendoDropDownList");
                        if (kendoDropDown) {
                            return kendoDropDown.text();
                        }
                    }
                    return "NOT FOUND";
                }
            ''')
            print(f"Court Location: {court_location}")
        except Exception as e:
            print(f"Court Location: ERROR - {e}")

        # Get Case Status dropdown selected text
        try:
            case_status = page.evaluate('''
                () => {
                    const dropdown = document.querySelector("#caseCriteria_CaseStatus");
                    if (dropdown) {
                        const kendoDropDown = $(dropdown).data("kendoDropDownList");
                        if (kendoDropDown) {
                            return kendoDropDown.text();
                        }
                    }
                    return "NOT FOUND";
                }
            ''')
            print(f"Case Status: {case_status}")
        except Exception as e:
            print(f"Case Status: ERROR - {e}")

        # Get Case Type dropdown selected text
        try:
            case_type = page.evaluate('''
                () => {
                    const dropdown = document.querySelector("#caseCriteria_CaseType");
                    if (dropdown) {
                        const kendoDropDown = $(dropdown).data("kendoDropDownList");
                        if (kendoDropDown) {
                            return kendoDropDown.text();
                        }
                    }
                    return "NOT FOUND";
                }
            ''')
            print(f"Case Type: {case_type}")
        except Exception as e:
            print(f"Case Type: ERROR - {e}")

        print("\n" + "="*60)
        print("BROWSER PAUSED - Manually inspect the form")
        print("Press Ctrl+C when done...")
        print("="*60 + "\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nClosing browser...")
            browser.close()

if __name__ == '__main__':
    debug_form_values()
