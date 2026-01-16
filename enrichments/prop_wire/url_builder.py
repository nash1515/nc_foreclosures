"""URL construction for PropWire."""

import re
from enrichments.prop_wire.config import PROPERTY_URL_TEMPLATE


def slugify_address(address: str) -> str:
    """
    Convert address to URL-friendly slug.

    Examples:
        "162 Williford Ln, Spring Lake, NC 28390" -> "162-Williford-Ln-Spring-Lake-NC-28390"
        "1225 April Loop" -> "1225-April-Loop"

    Args:
        address: Full or partial address string

    Returns:
        Slugified address for URL
    """
    # Remove non-alphanumeric characters except spaces
    cleaned = re.sub(r'[^\w\s-]', '', address)
    # Replace spaces with hyphens
    slug = re.sub(r'\s+', '-', cleaned.strip())
    return slug


def build_property_url(address_slug: str, property_id: str) -> str:
    """
    Build direct URL to PropWire property page.

    PropWire URLs format:
    https://propwire.com/realestate/{slugified-address}/{property_id}/property-details

    Args:
        address_slug: Slugified address (e.g., "162-Williford-Ln-Spring-Lake-NC-28390")
        property_id: Unique property ID from API (e.g., "204504433")

    Returns:
        Property detail URL
    """
    return PROPERTY_URL_TEMPLATE.format(
        address_slug=address_slug,
        property_id=property_id
    )


def extract_property_id_from_url(url: str) -> str | None:
    """
    Extract property ID from PropWire URL.

    Args:
        url: PropWire property URL

    Returns:
        Property ID if found, None otherwise
    """
    # Match format: /realestate/{address}/{property_id}/property-details
    match = re.search(r'/realestate/[^/]+/(\d+)/property-details', url)
    if match:
        return match.group(1)
    return None
