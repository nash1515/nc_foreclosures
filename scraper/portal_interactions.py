"""Portal interaction functions for NC Courts Portal."""

import time
from scraper.portal_selectors import *
from scraper.captcha_solver import solve_recaptcha
from common.logger import setup_logger

logger = setup_logger(__name__)


def click_advanced_filter(page):
    """Click the Advanced Filter Options link."""
    logger.info("Clicking Advanced Filter Options...")
    page.click(ADVANCED_FILTER_LINK)
    time.sleep(1)
    logger.info("  ✓ Advanced filters opened")


def fill_search_form(page, county_name, start_date, end_date, search_text):
    """
    Fill out the search form.

    Args:
        page: Playwright page object
        county_name: County name (e.g., 'Wake County')
        start_date: Start date object
        end_date: End date object
        search_text: Search text (e.g., '24SP*')
    """
    logger.info("Filling search form...")

    # Fill search criteria (case number pattern)
    page.fill(SEARCH_CRITERIA_INPUT, search_text)
    logger.info(f"  Search text: {search_text}")

    # Fill date range
    page.fill(FILE_DATE_START, start_date.strftime('%m/%d/%Y'))
    page.fill(FILE_DATE_END, end_date.strftime('%m/%d/%Y'))
    logger.info(f"  Date range: {start_date} to {end_date}")

    # Select county from Court Location dropdown
    # This is a custom dropdown - need to interact with it properly
    logger.info(f"  Selecting county: {county_name}")
    try:
        # Click the dropdown to open it
        page.click(COURT_LOCATION_DROPDOWN)
        time.sleep(0.5)

        # Select the county option
        # The dropdown uses a custom list, so we click on the text
        page.click(f'li:has-text("{county_name}")')
        time.sleep(0.5)
        logger.info(f"    ✓ Selected {county_name}")
    except Exception as e:
        logger.warning(f"  County selection may have failed: {e}")

    # Select Case Status: Pending
    try:
        page.click(CASE_STATUS_DROPDOWN)
        time.sleep(0.5)
        page.click(f'li:has-text("{PENDING_STATUS}")')
        time.sleep(0.5)
        logger.info(f"    ✓ Selected status: {PENDING_STATUS}")
    except Exception as e:
        logger.warning(f"  Status selection may have failed: {e}")

    # Select Case Type: Special Proceedings (non-confidential)
    # This requires finding the case type selector
    try:
        # Look for case type dropdown
        page.click('#caseCriteria_CaseType')
        time.sleep(0.5)
        page.click(f'li:has-text("{SPECIAL_PROCEEDINGS}")')
        time.sleep(0.5)
        logger.info(f"    ✓ Selected type: {SPECIAL_PROCEEDINGS}")
    except Exception as e:
        logger.warning(f"  Case type selection may have failed: {e}")

    logger.info("  ✓ Form filled")


def solve_and_submit_captcha(page):
    """
    Solve reCAPTCHA and submit the form.

    Args:
        page: Playwright page object

    Returns:
        bool: True if successful
    """
    logger.info("Solving reCAPTCHA...")

    try:
        # Get captcha token from CapSolver
        token = solve_recaptcha(PORTAL_URL, RECAPTCHA_SITE_KEY)

        if not token:
            logger.error("Failed to get CAPTCHA token")
            return False

        # Inject token into the hidden response field
        page.evaluate(f'''
            document.querySelector("{RECAPTCHA_RESPONSE_FIELD}").value = "{token}";
        ''')

        logger.info("  ✓ CAPTCHA token injected")

        # Submit the form
        logger.info("Submitting search...")
        page.click(SUBMIT_BUTTON)
        page.wait_for_load_state('networkidle', timeout=30000)

        logger.info("  ✓ Search submitted")
        return True

    except Exception as e:
        logger.error(f"CAPTCHA/submit failed: {e}")
        return False


def check_for_error(page):
    """
    Check if an error message is displayed.

    Args:
        page: Playwright page object

    Returns:
        tuple: (bool: has_error, str: error_message)
    """
    try:
        error_elem = page.locator(ERROR_MESSAGE).first
        if error_elem.is_visible():
            error_text = error_elem.inner_text()
            logger.warning(f"Error detected: {error_text}")
            return True, error_text
    except:
        pass

    return False, None


def extract_total_count_from_page(page):
    """
    Extract total case count from results page.

    Looks for text like "1 - 10 of 154 items"

    Args:
        page: Playwright page object

    Returns:
        int: Total count or None
    """
    try:
        summary_elem = page.locator(RESULTS_COUNT_TEXT).first
        if summary_elem.is_visible():
            text = summary_elem.inner_text()
            logger.debug(f"Results summary text: {text}")

            # Parse "1 - 10 of 154 items"
            import re
            match = re.search(r'of\s+(\d+)\s+items', text, re.IGNORECASE)
            if match:
                total = int(match.group(1))
                logger.info(f"Total cases found: {total}")
                return total
    except Exception as e:
        logger.error(f"Failed to extract total count: {e}")

    return None


def go_to_next_page(page):
    """
    Navigate to next page of results.

    Args:
        page: Playwright page object

    Returns:
        bool: True if next page exists and was clicked
    """
    try:
        next_button = page.locator(NEXT_PAGE_BUTTON).first
        if next_button.is_visible():
            next_button.click()
            page.wait_for_load_state('networkidle', timeout=30000)
            logger.info("  ✓ Navigated to next page")
            return True
    except:
        pass

    logger.info("  No more pages")
    return False
