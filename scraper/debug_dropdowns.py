"""Debug script to inspect Kendo dropdown structure."""

from playwright.sync_api import sync_playwright
import time

def inspect_dropdowns():
    """Open portal and inspect dropdown HTML structure."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Navigating to portal...")
        page.goto('https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29', wait_until='networkidle')

        # Click advanced
        print("\nClicking Advanced...")
        page.click('a:has-text("Advanced")')
        time.sleep(2)

        # Inspect each dropdown
        dropdowns = [
            ('Court Location', '#caseCriteria_CourtLocation'),
            ('Case Status', '#caseCriteria_CaseStatus'),
            ('Case Type', '#caseCriteria_CaseType')
        ]

        for name, selector in dropdowns:
            print(f"\n{'='*60}")
            print(f"Inspecting: {name}")
            print(f"Selector: {selector}")
            print(f"{'='*60}")

            try:
                # Get the element HTML
                element = page.locator(selector).first
                if element.count() > 0:
                    outer_html = element.evaluate('el => el.outerHTML')
                    print(f"\nOuter HTML:")
                    print(outer_html[:500])  # First 500 chars

                    # Try clicking
                    print(f"\nAttempting to click...")
                    element.click(timeout=5000)
                    time.sleep(1)

                    # Look for opened dropdown list
                    print(f"\nLooking for dropdown list...")

                    # Check various Kendo list selectors
                    list_selectors = [
                        'ul.k-list-ul',
                        'ul.k-list',
                        '.k-animation-container',
                        '.k-popup'
                    ]

                    for list_sel in list_selectors:
                        list_elem = page.locator(list_sel).first
                        if list_elem.count() > 0 and list_elem.is_visible():
                            print(f"  ✓ Found visible: {list_sel}")
                            list_html = list_elem.evaluate('el => el.outerHTML')
                            print(f"    HTML: {list_html[:300]}")
                        else:
                            print(f"  ✗ Not found/visible: {list_sel}")

                    # Close dropdown
                    page.keyboard.press('Escape')
                    time.sleep(0.5)

                else:
                    print(f"  ✗ Element not found")

            except Exception as e:
                print(f"  ERROR: {e}")

        print(f"\n{'='*60}")
        print("Inspection complete. Press Ctrl+C to close browser...")
        print(f"{'='*60}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nClosing...")
            browser.close()

if __name__ == '__main__':
    inspect_dropdowns()
