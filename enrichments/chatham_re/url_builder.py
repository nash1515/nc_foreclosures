"""URL construction for Chatham County Real Estate."""

import re
from urllib.parse import quote_plus
from enrichments.chatham_re.config import SEARCH_URL, PROPERTY_URL_TEMPLATE


def build_search_url(query: str) -> str:
    """
    Build search URL for Chatham County portal.

    Args:
        query: Search string (address, parcel number, or owner name)

    Returns:
        Full search URL with encoded query parameter
    """
    return f"{SEARCH_URL}?q={quote_plus(query)}"


def build_property_url(parcel_id: str) -> str:
    """
    Build direct URL to Chatham County property page.

    Chatham County uses DEVNET wEdge portal with direct parcel ID URLs.
    Format: https://chathamnc.devnetwedge.com/parcel/view/{parcel_id}/2025

    Args:
        parcel_id: 7-digit Parcel ID (e.g., "0074237")

    Returns:
        Property detail URL
    """
    return PROPERTY_URL_TEMPLATE.format(parcel_id=parcel_id)


def extract_parcel_id_from_url(url: str) -> str | None:
    """
    Extract Parcel ID from Chatham County property URL.

    Args:
        url: Property URL (e.g., "https://chathamnc.devnetwedge.com/parcel/view/0074237/2025")

    Returns:
        Parcel ID if found, None otherwise
    """
    match = re.search(r'/parcel/view/(\d+)/', url)
    if match:
        return match.group(1)
    return None
