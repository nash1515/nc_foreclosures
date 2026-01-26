"""URL construction for Lee County Real Estate."""

import re
from datetime import datetime


def build_property_url(parid: str) -> str:
    """
    Build direct URL to Lee County property page.

    Uses the UseSearch=no&pin= format which bypasses session-based URLs
    and provides a direct link to the property page.

    Args:
        parid: Parcel ID (e.g., "964267347000")

    Returns:
        Property detail URL
    """
    current_year = datetime.now().year
    return f'https://taxaccess.leecountync.gov/PT/Datalets/Datalet.aspx?mode=&UseSearch=no&pin={parid}&jur=000&taxyr={current_year}'


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
