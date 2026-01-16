"""HTTP-based scraper for Chatham County Real Estate portal."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

from enrichments.chatham_re.config import TIMEOUT_SECONDS
from enrichments.chatham_re.url_builder import build_search_url, build_property_url


logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from Chatham County property search."""
    success: bool
    parcel_id: Optional[str] = None
    url: Optional[str] = None
    matches_found: int = 0
    error: Optional[str] = None


def search_by_address(street_number: str, street_name: str, direction: Optional[str] = None) -> SearchResult:
    """
    Search Chatham County portal by property address.

    The DEVNET wEdge portal supports simple GET requests with query parameter.
    Search results are returned as HTML table rows.

    Strategy:
        1. Search by just the street number (most reliable)
        2. Parse HTML response for matching parcel links
        3. Filter results by street name for unique match

    Args:
        street_number: Street number (e.g., "1225")
        street_name: Street name (e.g., "April Loop")
        direction: Directional prefix (e.g., "N", "E", "W", "S") - optional

    Returns:
        SearchResult with parcel_id and URL if single match found
    """
    # Search by street number AND street name for precise matching
    # The portal supports multi-word queries like "88 Maple Springs"
    search_query = f"{street_number} {street_name}"

    logger.info(f"Searching Chatham County for: {search_query}")

    try:
        search_url = build_search_url(search_query)
        logger.debug(f"Search URL: {search_url}")

        response = requests.get(search_url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Check for no results message
        no_results = soup.find(string=re.compile(r'No results found', re.IGNORECASE))
        if no_results:
            logger.info("No results found")
            return SearchResult(
                success=False,
                matches_found=0,
                error="No results found"
            )

        # Find all parcel links in the results table
        # Links are in format: /search/ViewQuickSearchResult?...&property_key=0074237&...
        parcel_links = soup.find_all('a', href=re.compile(r'property_key=\d+'))

        if not parcel_links:
            logger.info("No parcel links found in results")
            return SearchResult(
                success=False,
                matches_found=0,
                error="No parcel links found"
            )

        # Build list of matches with address info
        matches = []
        for link in parcel_links:
            # Extract parcel ID from href
            href = link.get('href', '')
            parcel_match = re.search(r'property_key=(\d+)', href)
            if not parcel_match:
                continue

            parcel_id = parcel_match.group(1)

            # Get the row containing this link to find address
            row = link.find_parent('tr')
            if not row:
                continue

            # Find address cell - it's the cell with full address text
            row_text = row.get_text(' ', strip=True).upper()

            # Check if this row's address matches our street name
            street_name_upper = street_name.upper()
            # Handle multi-word street names (e.g., "Devils Tramping Ground")
            street_words = street_name_upper.split()

            # Check if all words of the street name appear in the row
            if all(word in row_text for word in street_words):
                # Check street number matches
                if street_number in row_text:
                    matches.append({
                        'parcel_id': parcel_id,
                        'row_text': row_text
                    })

        logger.debug(f"Found {len(matches)} matches for {street_number} {street_name}")

        if len(matches) == 0:
            # No matches for our street - might need to search differently
            logger.info(f"No matches found for street: {street_name}")
            return SearchResult(
                success=False,
                matches_found=0,
                error=f"No matches found for {street_number} {street_name}"
            )

        if len(matches) == 1:
            # Single match - success!
            parcel_id = matches[0]['parcel_id']
            url = build_property_url(parcel_id)
            logger.info(f"Single match found - Parcel ID: {parcel_id}")
            return SearchResult(
                success=True,
                parcel_id=parcel_id,
                url=url,
                matches_found=1
            )

        # Multiple matches - need manual review
        logger.info(f"Multiple matches found: {len(matches)}")
        return SearchResult(
            success=False,
            matches_found=len(matches),
            error=f"{len(matches)} matches found for {street_number} {street_name}"
        )

    except requests.Timeout:
        logger.error("Timeout during Chatham County search")
        return SearchResult(
            success=False,
            error="Request timeout"
        )
    except requests.RequestException as e:
        logger.error(f"Request error during Chatham County search: {e}")
        return SearchResult(
            success=False,
            error=f"Request error: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Error during Chatham County search: {e}")
        return SearchResult(
            success=False,
            error=f"Error: {str(e)}"
        )
