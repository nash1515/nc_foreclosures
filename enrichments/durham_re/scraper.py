"""
Playwright-based scraper for Durham County Tax/CAMA portal.

Uses headless browser automation because the PARCELPK value is only
obtainable by clicking through to the property page.
"""

import logging
import re
from dataclasses import dataclass
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from enrichments.durham_re.config import BASE_URL, HEADLESS, TIMEOUT_MS
from enrichments.durham_re.url_builder import extract_parcelpk_from_url

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a Durham property search."""
    success: bool
    parcelpk: str | None = None
    url: str | None = None
    matches_found: int = 0
    error: str | None = None


def search_by_address(stnum: str, street_name: str) -> SearchResult:
    """
    Search Durham Tax/CAMA portal by address and extract PARCELPK.

    Per Durham's instructions, do not include:
    - Street type (Rd, Dr, St, etc.)
    - Street directions (N, S, E, W, etc.)

    Args:
        stnum: Street number (e.g., "2706")
        street_name: Street name without type/direction (e.g., "HINSON")

    Returns:
        SearchResult with PARCELPK if single match found
    """
    logger.info(f"Searching Durham CAMA for: {stnum} {street_name}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            # Navigate to search page
            page.goto(BASE_URL)

            # Click the "Location Address" tab to reveal address search fields
            # The page defaults to "Owner/Business Name" tab
            location_tab = page.get_by_role('link', name='Location Address')
            location_tab.click()

            # Fill in the address fields (now visible after clicking tab)
            street_num_input = page.get_by_role('textbox', name='Optional Street Number')
            street_name_input = page.get_by_role('textbox', name='Do not include Street Type')

            street_num_input.fill(stnum)
            street_name_input.fill(street_name)

            # Click the Address search button
            search_button = page.locator('#ctl00_ContentPlaceHolder1_AddressButton')
            search_button.click()

            # Wait for results page to load (redirects to StreetSearchResults.aspx)
            page.wait_for_load_state('networkidle')

            # Check for "No records found" or count results
            # The results page shows "X Records Matched Search Criteria"
            no_records = page.locator('text=0 Records Matched')
            if no_records.is_visible():
                logger.info(f"No records found for {stnum} {street_name}")
                browser.close()
                return SearchResult(success=False, matches_found=0, error="No records found")

            # Find the results table - it's nested inside the page
            # Look for table rows with parcel links
            parcel_links = page.locator('a[href*="PropertySummary.aspx?PARCELPK="]')
            match_count = parcel_links.count()

            logger.info(f"Found {match_count} matches for {stnum} {street_name}")

            if match_count == 0:
                browser.close()
                return SearchResult(success=False, matches_found=0, error="No records found")

            if match_count > 1:
                # Multiple matches - need human review
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=match_count,
                    error=f"Multiple matches ({match_count}) found"
                )

            # Single match - click through to get PARCELPK
            # The parcel link is already found above
            parcel_link = parcel_links.first

            # Click the parcel link
            parcel_link.click()

            # Wait for PropertySummary page to load
            page.wait_for_load_state('networkidle')

            # Extract PARCELPK from the URL
            current_url = page.url
            parcelpk = extract_parcelpk_from_url(current_url)

            browser.close()

            if parcelpk:
                logger.info(f"Found PARCELPK={parcelpk} for {stnum} {street_name}")
                return SearchResult(
                    success=True,
                    parcelpk=parcelpk,
                    url=current_url,
                    matches_found=1
                )
            else:
                return SearchResult(
                    success=False,
                    matches_found=1,
                    error=f"Could not extract PARCELPK from URL: {current_url}"
                )

    except PlaywrightTimeout as e:
        logger.error(f"Timeout searching for {stnum} {street_name}: {e}")
        return SearchResult(success=False, error=f"Timeout: {e}")

    except Exception as e:
        logger.error(f"Error searching for {stnum} {street_name}: {e}")
        return SearchResult(success=False, error=str(e))
