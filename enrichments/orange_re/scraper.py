"""Playwright-based scraper for Orange County Real Estate portal."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from enrichments.orange_re.config import (
    BASE_URL,
    HEADLESS,
    TIMEOUT_MS,
)
from enrichments.orange_re.url_builder import extract_parcel_id_from_url


logger = logging.getLogger(__name__)

# Common street type suffixes to strip for cleaner searches
STREET_TYPES = {
    'ST', 'STREET', 'AVE', 'AVENUE', 'RD', 'ROAD', 'DR', 'DRIVE',
    'LN', 'LANE', 'CT', 'COURT', 'CIR', 'CIRCLE', 'WAY', 'PL', 'PLACE',
    'BLVD', 'BOULEVARD', 'TRL', 'TRAIL', 'PKWY', 'PARKWAY', 'HWY', 'HIGHWAY',
    'TER', 'TERRACE', 'RUN', 'PATH', 'LOOP', 'PASS', 'PT', 'POINT',
}

# Common NC city names that might get incorrectly included in street name
NC_CITIES = {
    'CHAPEL HILL', 'HILLSBOROUGH', 'CARRBORO', 'DURHAM', 'MEBANE',
    'EFLAND', 'CEDAR GROVE', 'HURDLE MILLS', 'WHITE CROSS', 'RALEIGH',
}


def _clean_street_name(street_name: str) -> str:
    """
    Clean up street name for Orange County search.

    The portal works best with just the core street name, without:
    - Street type suffixes (Way, Dr, St, etc.)
    - City names that got incorrectly parsed into the street name

    Args:
        street_name: Raw street name from parser (might include suffix/city)

    Returns:
        Cleaned street name suitable for portal search
    """
    if not street_name:
        return street_name

    # Work with uppercase for matching
    name_upper = street_name.upper()

    # Remove any NC city names that got appended
    for city in NC_CITIES:
        if name_upper.endswith(f' {city}'):
            name_upper = name_upper[:-len(city) - 1]
            break

    # Split into words and remove trailing street type
    words = name_upper.split()
    if words and words[-1] in STREET_TYPES:
        words = words[:-1]

    # Return in title case for cleaner display
    return ' '.join(words).title()


@dataclass
class SearchResult:
    """Result from Orange County property search."""
    success: bool
    parcel_id: Optional[str] = None
    url: Optional[str] = None
    matches_found: int = 0
    error: Optional[str] = None


def search_by_address(street_number: str, street_name: str, direction: Optional[str] = None) -> SearchResult:
    """
    Search Orange County portal by property address.

    The Spatialest portal uses a search-as-you-type interface. We type the address
    in the combobox and click Search. If there's exactly one match, the portal
    redirects directly to the property page.

    Args:
        street_number: Street number (e.g., "641")
        street_name: Street name (e.g., "Ethel Christine")
        direction: Directional prefix (e.g., "N", "E", "W", "S") - optional

    Returns:
        SearchResult with parcel_id and URL if single match found
    """
    # Clean up street name - remove suffixes and city names that may have been included
    clean_name = _clean_street_name(street_name)

    # Build search term - portal expects abbreviated directions (N, S, E, W)
    if direction:
        search_term = f"{street_number} {direction} {clean_name}"
    else:
        search_term = f"{street_number} {clean_name}"

    logger.info(f"Searching Orange County for: {search_term}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            page = browser.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            # Navigate to search page
            logger.debug(f"Navigating to {BASE_URL}")
            page.goto(BASE_URL)
            page.wait_for_load_state('networkidle')

            # Find and fill the search combobox
            search_box = page.get_by_role('combobox', name='Search for a property')
            logger.debug(f"Filling search: {search_term}")
            search_box.fill(search_term)

            # Click the Search button
            logger.debug("Clicking Search button")
            page.get_by_role('button', name='Search').click()

            # Wait for either:
            # 1. Redirect to property page (single match)
            # 2. Search results page (multiple matches or no matches)
            try:
                # Wait for URL to change - could be property page or results page
                page.wait_for_url(re.compile(r'#/(property|search)'), timeout=15000)
            except PlaywrightTimeout:
                logger.warning("Timeout waiting for search results")
                browser.close()
                return SearchResult(
                    success=False,
                    error="Timeout waiting for search results"
                )

            current_url = page.url
            logger.debug(f"Current URL after search: {current_url}")

            # Check if we landed on a property page (single match)
            if '/property/' in current_url and '/search' not in current_url:
                parcel_id = extract_parcel_id_from_url(current_url)
                if parcel_id:
                    logger.info(f"Single match found - Parcel ID: {parcel_id}")
                    browser.close()
                    return SearchResult(
                        success=True,
                        parcel_id=parcel_id,
                        url=current_url,
                        matches_found=1
                    )
                else:
                    logger.warning(f"Could not extract parcel ID from URL: {current_url}")
                    browser.close()
                    return SearchResult(
                        success=False,
                        matches_found=1,
                        error="Could not extract parcel ID from URL"
                    )

            # We're on the search results page - check for no results or multiple
            page.wait_for_load_state('networkidle')

            # Wait a bit for dynamic content to load
            page.wait_for_timeout(2000)

            # Check for "No results found" alert
            no_results = page.locator('text=No results found')
            if no_results.count() > 0:
                logger.info("No results found")
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=0,
                    error="No results found"
                )

            # Check page content to see if we're on a single property detail view
            # (The portal is a SPA that may keep /search/ in URL but show property details)
            page_text = page.locator('body').inner_text()
            logger.debug(f"Page text (first 500 chars): {page_text[:500]}")

            # Look for Parcel ID in the page content - indicates we're on a property page
            parcel_match = re.search(r'Parcel ID\s*[:\s]*(\d{10})', page_text)
            if parcel_match:
                parcel_id = parcel_match.group(1)
                url = f"https://property.spatialest.com/nc/orange/#/property/{parcel_id}"
                logger.info(f"Found property via Parcel ID in content: {parcel_id}")
                browser.close()
                return SearchResult(
                    success=True,
                    parcel_id=parcel_id,
                    url=url,
                    matches_found=1
                )

            # If no parcel ID found, look for result list links
            # The href format is #/property/XXXXXXXXXX
            property_links = page.locator('a[href*="#/property/"]')
            link_count = property_links.count()
            logger.debug(f"Found {link_count} property links")

            if link_count == 0:
                logger.info("No property links found - likely no results")
                browser.close()
                return SearchResult(
                    success=False,
                    matches_found=0,
                    error="No results found"
                )

            if link_count == 1:
                # Single result in list - extract parcel ID from link
                href = property_links.first.get_attribute('href')
                logger.debug(f"Single result href: {href}")
                if href:
                    # Match either /property/XXXXXXXXXX or #/property/XXXXXXXXXX
                    parcel_match = re.search(r'#?/property/(\d{10})', href)
                    if parcel_match:
                        parcel_id = parcel_match.group(1)
                        url = f"https://property.spatialest.com/nc/orange/#/property/{parcel_id}"
                        logger.info(f"Single result - Parcel ID: {parcel_id}")
                        browser.close()
                        return SearchResult(
                            success=True,
                            parcel_id=parcel_id,
                            url=url,
                            matches_found=1
                        )

            # Multiple results
            logger.info(f"Multiple results found: {link_count}")
            browser.close()
            return SearchResult(
                success=False,
                matches_found=link_count,
                error=f"{link_count} matches found"
            )

    except PlaywrightTimeout as e:
        logger.error(f"Timeout during Orange County search: {e}")
        return SearchResult(
            success=False,
            error=f"Timeout: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Error during Orange County search: {e}")
        return SearchResult(
            success=False,
            error=f"Error: {str(e)}"
        )
