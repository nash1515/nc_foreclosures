"""URL construction for Lee County Real Estate."""

import re


def build_property_url(parid: str, index: int = 1) -> str:
    """
    Build direct URL to Lee County property page.

    Note: Lee County uses session-based URLs that require a search first.
    This URL format is what gets returned after search, but may not work
    as a direct link without the search session.

    Args:
        parid: Parcel ID (e.g., "964267347000")
        index: Result index in search (default 1)

    Returns:
        Property detail URL
    """
    return f'https://taxaccess.leecountync.gov/pt/Datalets/Datalet.aspx?sIndex=0&idx={index}'


def extract_parid_from_text(text: str) -> str | None:
    """
    Extract Parcel ID from page text.

    Args:
        text: Page text containing Parcel ID

    Returns:
        Parcel ID if found, None otherwise
    """
    # Look for pattern like "ParID / PIN: 964267347000 /"
    match = re.search(r'ParID\s*/\s*PIN:\s*(\d+)', text, re.IGNORECASE)
    if match:
        return match.group(1)

    # Alternative pattern: "PARID: 964267347000"
    match = re.search(r'PARID:\s*(\d+)', text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None
