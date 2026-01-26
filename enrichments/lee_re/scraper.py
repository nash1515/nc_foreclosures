"""Playwright-based scraper for Lee County Real Estate portal."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from enrichments.lee_re.config import (
    SEARCH_URL,
    STREET_NUMBER_INPUT,
    STREET_NAME_INPUT,
    SEARCH_BUTTON,
    HEADLESS,
    TIMEOUT_MS,
)
from enrichments.lee_re.url_builder import build_property_url, extract_parid_from_text


logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from Lee County property search."""
    success: bool
    account_id: Optional[str] = None
    url: Optional[str] = None
    matches_found: int = 0
    error: Optional[str] = None


def search_by_address(street_number: str, street_name: str, direction: Optional[str] = None) -> SearchResult:
    """
    Search Lee County portal by property address.

    Args:
        street_number: Street number (e.g., "409")
        street_name: Street name without directional prefix (e.g., "Harrington")
        direction: Directional prefix (e.g., "W", "E", "N", "S") - maps to -DIR- dropdown

    Returns:
        SearchResult with account_id and URL if single match found
    """
    dir_display = f" {direction}" if direction else ""
    logger.info(f"Searching Lee County for: {street_number}{dir_display} {street_name}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            page = browser.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            # Navigate to search page
            logger.debug(f"Navigating to {SEARCH_URL}")
            page.goto(SEARCH_URL)
            page.wait_for_load_state('networkidle')

            # Fill in address fields using role-based locators
            logger.debug(f"Filling street number: {street_number}")
            page.get_by_role('textbox', name='Address: No').fill(street_number)

            logger.debug(f"Filling street name: {street_name}")
            page.get_by_role('textbox', name='Street').fill(street_name)

            # Select direction from dropdown if provided
            if direction:
                # Map common abbreviations to dropdown values
                dir_map = {
                    'N': 'NORTH',
                    'S': 'SOUTH',
                    'E': 'EAST',
                    'W': 'WEST',
                    'NORTH': 'NORTH',
                    'SOUTH': 'SOUTH',
                    'EAST': 'EAST',
                    'WEST': 'WEST',
                }
                dir_value = dir_map.get(direction.upper())
                if dir_value:
                    logger.debug(f"Selecting direction: {dir_value}")
                    page.locator('select').filter(has_text='-DIR-').select_option(dir_value)

            # Click search button
            logger.debug("Clicking search button")
            page.get_by_role('button', name='Search').click()

            # Wait for results - look for either results text or "no records" message
            # The Tyler portal renders results dynamically, so we need to wait for them
            try:
                page.wait_for_selector('text=Displaying', timeout=10000)
            except PlaywrightTimeout:
                # No results found - check if page says "No records found" or similar
                logger.warning("No 'Displaying' text found - likely no results")
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=0,
                    error="No results found"
                )

            # Check if we got results
            # Look for the results summary text "Displaying X - Y of Z"
            # Use inner_text() to get visible text (not page.content() which returns HTML)
            page_text = page.locator('body').inner_text()

            # Extract result count from "Displaying 1 - 1 of 1" or similar
            count_match = re.search(r'Displaying\s+\d+\s*-\s*\d+\s+of\s+(\d+)', page_text)
            if not count_match:
                logger.warning("No results count found in page")
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=0,
                    error="No results found"
                )

            total_results = int(count_match.group(1))
            logger.info(f"Found {total_results} result(s)")

            if total_results == 0:
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=0,
                    error="No matches found"
                )

            if total_results > 1:
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=total_results,
                    error=f"{total_results} matches found"
                )

            # Single match - extract parcel ID directly from results table
            # The parcel ID is visible in the search results, no need to click through
            try:
                # The parcel ID is in a cell within the data row
                # Format in page: "954813718400" in a cell
                parid_match = re.search(r'(\d{12})', page_text)  # 12-digit parcel ID

                if parid_match:
                    parid = parid_match.group(1)
                    logger.info(f"Extracted Parcel ID from results: {parid}")

                    # Build the direct property URL using parcel ID
                    property_url = build_property_url(parid)

                    browser.close()
                    return SearchResult(
                        success=True,
                        account_id=parid,
                        url=property_url,
                        matches_found=1
                    )
                else:
                    logger.warning("Could not extract Parcel ID from results page")
                    browser.close()
                    return SearchResult(
                        success=False,
                        matches_found=1,
                        error="Could not extract Parcel ID from results"
                    )
            except Exception as e:
                logger.error(f"Error extracting parcel ID: {e}")
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=1,
                    error=f"Could not extract parcel ID: {str(e)}"
                )

    except PlaywrightTimeout as e:
        logger.error(f"Timeout during Lee County search: {e}")
        return SearchResult(
            success=False,
            error=f"Timeout: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Error during Lee County search: {e}")
        return SearchResult(
            success=False,
            error=f"Error: {str(e)}"
        )
