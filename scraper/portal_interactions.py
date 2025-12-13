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


def fill_search_form(page, county_names, start_date, end_date, search_text, party_name=None):
    """
    Fill out the search form.

    Portal Form Structure (discovered via Playwright MCP):
    - Location: Uses CHECKBOXES (not dropdown). Must uncheck "All Locations" first.
    - Case Type/Status: Use Kendo ComboBox widgets (set via JavaScript).
    - Dates: Standard text inputs with MM/DD/YYYY format.
    - Search text: Required field at top.
    - Party Name: Optional text input for filtering by party last name.

    Args:
        page: Playwright page object
        county_names: County name (str) or list of county names (e.g., 'Wake County' or ['Wake County', 'Durham County'])
        start_date: Start date object
        end_date: End date object
        search_text: Search text (e.g., '24SP*')
        party_name: Optional party name to filter search (default: None)
    """
    # Normalize county_names to a list
    if isinstance(county_names, str):
        county_names = [county_names]

    logger.info("Filling search form...")

    # 1. Fill search criteria (required field at top)
    page.fill(SEARCH_CRITERIA_INPUT, search_text)
    logger.info(f"  Search text: {search_text}")

    # 2. Fill date range
    page.fill(FILE_DATE_START, start_date.strftime('%m/%d/%Y'))
    page.fill(FILE_DATE_END, end_date.strftime('%m/%d/%Y'))
    # Click elsewhere to close any calendar popup
    page.keyboard.press('Escape')
    logger.info(f"  Date range: {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}")

    # 3. Select counties using CHECKBOXES (not dropdown!)
    logger.info(f"  Selecting {len(county_names)} counties: {', '.join(county_names)}")
    try:
        # First, uncheck "All Locations" checkbox
        page.evaluate('''
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            for (const cb of checkboxes) {
                const label = cb.closest('label') || cb.parentElement;
                if (label && label.textContent.includes('All Locations')) {
                    if (cb.checked) {
                        cb.click();
                    }
                    break;
                }
            }
        ''')
        time.sleep(0.3)
        logger.info("    ✓ Unchecked 'All Locations'")

        # Now check each county checkbox
        for county_name in county_names:
            page.evaluate(f'''
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                for (const cb of checkboxes) {{
                    const label = cb.closest('label') || cb.parentElement;
                    if (label && label.textContent.includes('{county_name}')) {{
                        if (!cb.checked) {{
                            cb.click();
                        }}
                        break;
                    }}
                }}
            ''')
            time.sleep(0.2)
        logger.info(f"    ✓ Selected {len(county_names)} counties")
    except Exception as e:
        logger.error(f"  County selection failed: {e}")

    # 4. Select Case Type using Kendo ComboBox (NOT DropDownList!)
    try:
        logger.info(f"  Selecting type: {SPECIAL_PROCEEDINGS}")
        page.evaluate(f'''
            const widget = $('input[name="caseCriteria.CaseType"]').data('kendoComboBox');
            if (widget) {{
                widget.value("{SPECIAL_PROCEEDINGS}");
                widget.trigger("change");
            }}
        ''')
        logger.info(f"    ✓ Selected type: {SPECIAL_PROCEEDINGS}")
    except Exception as e:
        logger.warning(f"  Case type selection failed: {e}")

    # 5. Select Case Status using Kendo ComboBox
    # Status values are codes: "PEND" for Pending
    try:
        logger.info(f"  Selecting status: {PENDING_STATUS}")
        page.evaluate('''
            const widget = $('input[name="caseCriteria.CaseStatus"]').data('kendoComboBox');
            if (widget) {
                widget.value("PEND");  // "PEND" is the value for "Pending"
                widget.trigger("change");
            }
        ''')
        logger.info(f"    ✓ Selected status: {PENDING_STATUS}")
    except Exception as e:
        logger.warning(f"  Status selection failed: {e}")

    # 6. Fill party name if provided
    if party_name:
        try:
            logger.info(f"  Filtering by party name: {party_name}")
            page.fill(PARTY_NAME_INPUT, party_name)
            logger.info(f"    ✓ Party name filter applied")
        except Exception as e:
            logger.warning(f"  Party name filter failed: {e}")

    logger.info("  ✓ Form filled")


def solve_and_submit_captcha(page):
    """
    Solve reCAPTCHA and submit the form.

    Waits for Kendo Grid to initialize after submission.

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
        page.click(SUBMIT_BUTTON, timeout=30000)
        logger.info("  Submit button clicked, waiting for results...")

        # Wait for either: grid with results, grid with no-records message, or "no cases" text
        # The portal shows "No cases match your search" when there are no results
        logger.info("  Waiting for results or 'no cases' message...")

        # Poll for either condition - check every 2 seconds for up to 60 seconds
        max_wait = 60
        poll_interval = 2
        waited = 0

        while waited < max_wait:
            page_text = page.content()

            # Check for "no cases" message first
            if "No cases match your search" in page_text:
                logger.info("  ✓ Search completed - No cases match the search criteria")
                return "no_results"

            # Check if grid with data rows is present
            try:
                grid_row = page.locator('#CasesGrid tbody tr.k-master-row').first
                if grid_row.is_visible(timeout=100):
                    logger.debug("    Grid rows found")
                    break
            except:
                pass

            # Check for Kendo "no records" indicator
            try:
                no_records = page.locator('#CasesGrid .k-grid-norecords').first
                if no_records.is_visible(timeout=100):
                    logger.info("  ✓ Search completed - No cases match the search criteria (grid no-records)")
                    return "no_results"
            except:
                pass

            time.sleep(poll_interval)
            waited += poll_interval

        # Final check after loop
        if waited >= max_wait:
            page_text = page.content()
            if "No cases match your search" in page_text:
                logger.info("  ✓ Search completed - No cases match the search criteria")
                return "no_results"
            raise Exception(f"Timeout {max_wait}s waiting for search results")

        time.sleep(2)  # Give grid time to fully render

        logger.info("  ✓ Search submitted, results loaded")
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

    Kendo UI Grid pager info: "1 - 10 of 75 items"

    Args:
        page: Playwright page object

    Returns:
        int: Total count or None
    """
    try:
        # Kendo pager info element
        pager_info = page.locator('.k-pager-info').first
        if pager_info.is_visible():
            text = pager_info.inner_text()
            logger.debug(f"Kendo pager info: {text}")

            # Parse "1 - 10 of 75 items"
            import re
            match = re.search(r'of\s+(\d+)\s+items?', text, re.IGNORECASE)
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

    Kendo UI Grid uses .k-pager-wrap with arrow icons.
    Next button: a.k-link:has(.k-i-arrow-e):not(.k-state-disabled)

    Args:
        page: Playwright page object

    Returns:
        bool: True if next page exists and was clicked
    """
    try:
        # Look for next arrow button in Kendo pager that's not disabled
        next_button = page.locator('.k-pager-wrap a.k-link:has(.k-i-arrow-e):not(.k-state-disabled)').first
        if next_button.is_visible():
            next_button.click()
            page.wait_for_load_state('networkidle', timeout=60000)
            logger.info("  ✓ Navigated to next page")
            return True
    except Exception as e:
        logger.debug(f"Next page navigation failed: {e}")
        pass

    logger.info("  No more pages")
    return False
