"""
Playwright-based scraper for Harnett County CAMA portal.

Uses headless browser automation to search for properties by address.
The portal is a JavaScript SPA where URLs don't change during navigation,
but the "View Property Record" button opens a new tab with a direct prid URL.
"""

import logging
import re
from dataclasses import dataclass
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from enrichments.harnett_re.config import BASE_URL, HEADLESS, TIMEOUT_MS
from enrichments.harnett_re.url_builder import extract_prid_from_url

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a Harnett property search."""
    success: bool
    prid: str | None = None
    url: str | None = None
    matches_found: int = 0
    error: str | None = None


def search_by_address(address: str) -> SearchResult:
    """
    Search Harnett County CAMA portal by address and extract prid.

    The Harnett portal uses a single address input field (not separate
    street number and name fields like some other counties).

    Args:
        address: Full or partial address to search (e.g., "259 Golf")

    Returns:
        SearchResult with prid if single match found
    """
    logger.info(f"Searching Harnett CAMA for: {address}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            # Navigate to search page
            page.goto(BASE_URL)

            # Step 1: Select "Property Address" from dropdown
            # Default is "Property Owner Name"
            dropdown = page.locator('#searchType')
            dropdown.select_option('Property Address')

            # Wait for the address input field to appear
            page.wait_for_selector('#FormattedPropertyAddress')

            # Step 2: Enter the address
            address_input = page.locator('#FormattedPropertyAddress')
            address_input.fill(address)

            # Step 3: Click Submit
            submit_button = page.get_by_role('button', name='Submit')
            submit_button.click()

            # Wait for results table to load
            page.wait_for_load_state('networkidle')

            # Step 4: Check for results
            # Look for "Property Information Search Results" heading
            results_heading = page.locator('h3:has-text("Property Information Search Results")')

            if not results_heading.is_visible():
                # No results section appeared
                browser.close()
                return SearchResult(success=False, matches_found=0, error="No results found")

            # Count result rows by looking at the pagination text
            # Format: "records 1 - N of N" where N is total matches
            # Use text content search instead of regex locator
            body_text = page.locator('body').inner_text()
            records_match = re.search(r'records \d+ - \d+ of (\d+)', body_text)
            if records_match:
                match_count = int(records_match.group(1))
            else:
                match_count = 0

            logger.info(f"Found {match_count} matches for {address}")

            if match_count == 0:
                browser.close()
                return SearchResult(success=False, matches_found=0, error="No results found")

            if match_count > 1:
                # Multiple matches - need human review
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=match_count,
                    error=f"Multiple matches ({match_count}) found"
                )

            # Step 5: Single match - click the first data row to expand details
            # The data rows are in the second table (first is header)
            # Find rows that contain the PRC link (data rows, not header)
            data_row = page.locator('tr:has(a[href*="AppraisalCard"])').first
            data_row.click()

            # Wait for Parcel Information section to load
            page.wait_for_selector('h3:has-text("Parcel Information")')

            # Step 6: Extract prid from "View Property Record" button's onclick
            # Button HTML: <input onclick="window.open('...?prid=8067356', '_blank')" ...>
            view_record_btn = page.get_by_role('button', name='View Property Record for this Parcel')
            onclick_attr = view_record_btn.evaluate('el => el.getAttribute("onclick")')

            # Extract URL from onclick: window.open('URL', '_blank')
            url_match = re.search(r"window\.open\('([^']+)'", onclick_attr)
            if not url_match:
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=1,
                    error=f"Could not extract URL from onclick: {onclick_attr}"
                )

            property_url = url_match.group(1)
            prid = extract_prid_from_url(property_url)

            browser.close()

            if prid:
                logger.info(f"Found prid={prid} for {address}")
                return SearchResult(
                    success=True,
                    prid=prid,
                    url=property_url,
                    matches_found=1
                )
            else:
                return SearchResult(
                    success=False,
                    matches_found=1,
                    error=f"Could not extract prid from URL: {property_url}"
                )

    except PlaywrightTimeout as e:
        logger.error(f"Timeout searching for {address}: {e}")
        return SearchResult(success=False, error=f"Timeout: {e}")

    except Exception as e:
        logger.error(f"Error searching for {address}: {e}")
        return SearchResult(success=False, error=str(e))
