"""URL construction for Orange County Real Estate."""

import re
from enrichments.orange_re.config import PROPERTY_URL_TEMPLATE


def build_property_url(parcel_id: str) -> str:
    """
    Build direct URL to Orange County property page.

    Orange County uses Spatialest portal with direct parcel ID URLs.
    Format: https://property.spatialest.com/nc/orange/#/property/{parcel_id}

    Args:
        parcel_id: 10-digit Parcel ID (e.g., "9767585618")

    Returns:
        Property detail URL
    """
    return PROPERTY_URL_TEMPLATE.format(parcel_id=parcel_id)


def extract_parcel_id_from_url(url: str) -> str | None:
    """
    Extract Parcel ID from Orange County property URL.

    Args:
        url: Property URL (e.g., "https://property.spatialest.com/nc/orange/#/property/9767585618")

    Returns:
        Parcel ID if found, None otherwise
    """
    match = re.search(r'/property/(\d{10})(?:/|$|\?)', url)
    if match:
        return match.group(1)
    return None
