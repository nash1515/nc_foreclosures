"""Interactive portal exploration script to identify HTML structure."""

from playwright.sync_api import sync_playwright
from common.logger import setup_logger
import time

logger = setup_logger(__name__)

PORTAL_URL = 'https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29'


def explore_portal():
    """
    Launch browser to explore the NC Courts Portal.

    This script opens the portal in non-headless mode so we can:
    1. See the actual page structure
    2. Identify form field selectors
    3. Understand the search flow
    4. Identify reCAPTCHA elements
    5. See result page structure
    """
    logger.info("Launching browser to explore portal...")

    with sync_playwright() as p:
        # Launch in non-headless mode with slow motion for visibility
        browser = p.chromium.launch(
            headless=False,
            slow_mo=1000  # Slow down actions by 1 second
        )

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )

        page = context.new_page()

        logger.info(f"Navigating to {PORTAL_URL}")
        page.goto(PORTAL_URL, wait_until='networkidle')

        logger.info("Portal loaded. Exploring structure...")

        # Print page title
        title = page.title()
        logger.info(f"Page title: {title}")

        # Look for Advanced Filter Options button
        logger.info("\nLooking for 'Advanced Filter Options' button...")
        try:
            # Try common selectors
            advanced_filter_selectors = [
                "text='Advanced Filter Options'",
                "button:has-text('Advanced Filter Options')",
                "a:has-text('Advanced Filter Options')",
                ".advanced-filter",
                "#advanced-filter"
            ]

            for selector in advanced_filter_selectors:
                if page.locator(selector).count() > 0:
                    logger.info(f"✓ Found with selector: {selector}")
                    break
        except Exception as e:
            logger.error(f"Error finding advanced filter: {e}")

        # Look for reCAPTCHA
        logger.info("\nLooking for reCAPTCHA...")
        try:
            recaptcha_selectors = [
                ".g-recaptcha",
                "iframe[src*='recaptcha']",
                "[data-sitekey]"
            ]

            for selector in recaptcha_selectors:
                count = page.locator(selector).count()
                if count > 0:
                    logger.info(f"✓ Found {count} reCAPTCHA element(s) with: {selector}")

                    # Try to get site key
                    if '[data-sitekey]' in selector:
                        site_key = page.locator(selector).get_attribute('data-sitekey')
                        logger.info(f"  Site key: {site_key}")
        except Exception as e:
            logger.error(f"Error finding reCAPTCHA: {e}")

        logger.info("\n" + "="*60)
        logger.info("MANUAL EXPLORATION MODE")
        logger.info("="*60)
        logger.info("Browser will stay open for manual exploration.")
        logger.info("Use browser DevTools (F12) to inspect elements.")
        logger.info("Press Enter in this terminal when done exploring...")
        logger.info("="*60)

        # Keep browser open for manual exploration
        input()

        logger.info("Closing browser...")
        browser.close()


if __name__ == '__main__':
    explore_portal()
