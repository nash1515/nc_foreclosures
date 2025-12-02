"""Capture portal structure and save HTML for analysis."""

from playwright.sync_api import sync_playwright
from common.logger import setup_logger
from pathlib import Path
import time

logger = setup_logger(__name__)

PORTAL_URL = 'https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29'
OUTPUT_DIR = Path('portal_analysis')


def capture_portal_structure():
    """Capture portal HTML structure and screenshots."""

    OUTPUT_DIR.mkdir(exist_ok=True)
    logger.info(f"Output directory: {OUTPUT_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        # Use a real Chrome user-agent to avoid bot detection
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        logger.info(f"Navigating to {PORTAL_URL}")
        page.goto(PORTAL_URL, wait_until='networkidle')
        time.sleep(2)  # Let page fully render

        # Capture initial page
        logger.info("Capturing initial page state...")

        # Save HTML
        html = page.content()
        html_file = OUTPUT_DIR / '01_initial_page.html'
        html_file.write_text(html)
        logger.info(f"  Saved HTML: {html_file}")

        # Save screenshot
        screenshot_file = OUTPUT_DIR / '01_initial_page.png'
        page.screenshot(path=str(screenshot_file), full_page=True)
        logger.info(f"  Saved screenshot: {screenshot_file}")

        # Look for key elements
        logger.info("\nAnalyzing page structure...")

        # reCAPTCHA info
        try:
            site_key_elem = page.locator('[data-sitekey]').first
            if site_key_elem.count() > 0:
                site_key = site_key_elem.get_attribute('data-sitekey')
                logger.info(f"✓ reCAPTCHA Site Key: {site_key}")
        except:
            pass

        # Look for search form elements
        logger.info("\nLooking for form elements...")

        # Common form element selectors
        selectors_to_check = {
            'Search input': ['input[type="text"]', 'input[name*="search"]', '#search'],
            'Submit button': ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Search")'],
            'Date inputs': ['input[type="date"]', 'input[name*="date"]'],
            'Select/dropdown': ['select', '.dropdown'],
            'Advanced filter': ['text="Advanced"', 'button:has-text("Advanced")', 'a:has-text("Advanced")'],
        }

        found_elements = {}
        for name, selectors in selectors_to_check.items():
            for selector in selectors:
                try:
                    count = page.locator(selector).count()
                    if count > 0:
                        logger.info(f"  ✓ {name}: {count} found with '{selector}'")
                        found_elements[name] = selector
                        break
                except:
                    pass

        # Save element info
        info_file = OUTPUT_DIR / 'element_info.txt'
        with open(info_file, 'w') as f:
            f.write("NC Courts Portal - Element Analysis\n")
            f.write("="*60 + "\n\n")
            f.write(f"URL: {PORTAL_URL}\n")
            f.write(f"Page Title: {page.title()}\n\n")
            f.write("Found Elements:\n")
            for name, selector in found_elements.items():
                f.write(f"  {name}: {selector}\n")

        logger.info(f"\n  Saved element info: {info_file}")

        # Click Advanced Filter Options if found
        try:
            logger.info("\nAttempting to click 'Advanced Filter Options'...")

            # Try different selectors
            advanced_selectors = [
                'text="Advanced Filter Options"',
                'button:has-text("Advanced")',
                'a:has-text("Advanced")',
                '.advancedFilterButton',
                '#advancedFilter'
            ]

            clicked = False
            for selector in advanced_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.locator(selector).first.click()
                        logger.info(f"  ✓ Clicked using: {selector}")
                        clicked = True
                        time.sleep(2)
                        break
                except:
                    pass

            if clicked:
                # Capture advanced filter view
                html = page.content()
                html_file = OUTPUT_DIR / '02_advanced_filters.html'
                html_file.write_text(html)
                logger.info(f"  Saved advanced filter HTML: {html_file}")

                screenshot_file = OUTPUT_DIR / '02_advanced_filters.png'
                page.screenshot(path=str(screenshot_file), full_page=True)
                logger.info(f"  Saved advanced filter screenshot: {screenshot_file}")

        except Exception as e:
            logger.error(f"Error with advanced filters: {e}")

        logger.info("\n" + "="*60)
        logger.info("Portal structure captured successfully!")
        logger.info(f"Check {OUTPUT_DIR}/ for HTML and screenshots")
        logger.info("="*60)

        time.sleep(2)
        browser.close()


if __name__ == '__main__':
    capture_portal_structure()
