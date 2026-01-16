"""
Playwright-based scraper for PropWire property search.

Uses headless browser automation to interact with PropWire's autocomplete search
and intercept the API response to capture property IDs.
"""

import logging
import json
from dataclasses import dataclass
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from enrichments.prop_wire.config import BASE_URL, API_URL, HEADLESS, TIMEOUT_MS
from enrichments.prop_wire.url_builder import build_property_url, slugify_address

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a PropWire property search."""
    success: bool
    property_id: Optional[str] = None
    normalized_address: Optional[str] = None
    url: Optional[str] = None
    matches_found: int = 0
    error: Optional[str] = None


def search_by_address(address: str) -> SearchResult:
    """
    Search PropWire by address using autocomplete API.

    Strategy:
        1. Navigate to propwire.com
        2. Type address in search box
        3. Intercept API call to auto_complete endpoint
        4. Extract property ID and normalized address from response
        5. Build final property URL

    Args:
        address: Property address (e.g., "162 Williford Ln, Spring Lake, NC 28390")

    Returns:
        SearchResult with property_id and URL if single match found
    """
    logger.info(f"Searching PropWire for: {address}")

    # Store intercepted API response
    api_response_data = None

    def handle_response(response):
        """Capture API responses from auto_complete endpoint."""
        nonlocal api_response_data
        if API_URL in response.url:
            try:
                data = response.json()
                api_response_data = data
                logger.debug(f"Intercepted API response: {json.dumps(data, indent=2)}")
            except Exception as e:
                logger.error(f"Error parsing API response: {e}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            # Set up response listener before navigation
            page.on('response', handle_response)

            # Navigate to PropWire homepage
            logger.debug(f"Navigating to {BASE_URL}")
            page.goto(BASE_URL)

            # Wait for page to load
            page.wait_for_load_state('networkidle')

            # Find the search input box
            # PropWire typically has a search input in the header/navbar
            # Try multiple possible selectors
            search_input = None
            selectors = [
                'input[type="text"][placeholder*="Search"]',
                'input[type="search"]',
                'input.search-input',
                'input[name="search"]',
                '#search-input',
                'input[placeholder*="address"]'
            ]

            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if element.is_visible(timeout=2000):
                        search_input = element
                        logger.debug(f"Found search input with selector: {selector}")
                        break
                except:
                    continue

            if not search_input:
                # Try finding by role
                try:
                    search_input = page.get_by_role('searchbox')
                    logger.debug("Found search input by role='searchbox'")
                except:
                    pass

            if not search_input:
                browser.close()
                return SearchResult(
                    success=False,
                    error="Could not locate search input on PropWire homepage"
                )

            # Type address slowly to trigger autocomplete
            logger.debug(f"Typing address into search box")
            search_input.fill(address)

            # Wait a moment for the autocomplete dropdown to appear and API call to complete
            page.wait_for_timeout(2000)

            browser.close()

            # Process the intercepted API response
            if not api_response_data:
                logger.warning("No API response intercepted - autocomplete may not have triggered")
                return SearchResult(
                    success=False,
                    error="No autocomplete response captured"
                )

            # Parse API response structure
            # Expected format: {"data": [{"id": "204504433", "address": "162 Williford Ln..."}, ...]}
            if 'data' not in api_response_data:
                logger.error(f"Unexpected API response format: {api_response_data}")
                return SearchResult(
                    success=False,
                    error="Unexpected API response format"
                )

            results = api_response_data['data']

            if not results or len(results) == 0:
                logger.info(f"No results found for address: {address}")
                return SearchResult(
                    success=False,
                    matches_found=0,
                    error="No property found"
                )

            if len(results) > 1:
                logger.info(f"Multiple matches found ({len(results)}) for address: {address}")
                return SearchResult(
                    success=False,
                    matches_found=len(results),
                    error=f"{len(results)} matches found"
                )

            # Single match - extract property details
            result = results[0]
            property_id = result.get('id')
            normalized_address = result.get('address', '')

            if not property_id:
                logger.error(f"No property ID in API response: {result}")
                return SearchResult(
                    success=False,
                    error="Property ID not found in API response"
                )

            # Build the property URL
            address_slug = slugify_address(normalized_address or address)
            url = build_property_url(address_slug, property_id)

            logger.info(f"Found property ID={property_id} for {address}")
            logger.debug(f"Property URL: {url}")

            return SearchResult(
                success=True,
                property_id=property_id,
                normalized_address=normalized_address,
                url=url,
                matches_found=1
            )

    except PlaywrightTimeout as e:
        logger.error(f"Timeout searching for {address}: {e}")
        return SearchResult(success=False, error=f"Timeout: {e}")

    except Exception as e:
        logger.exception(f"Error searching for {address}: {e}")
        return SearchResult(success=False, error=str(e))
