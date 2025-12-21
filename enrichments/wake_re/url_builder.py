"""URL construction for Wake County Real Estate portal."""

from typing import Optional
from urllib.parse import quote_plus

from enrichments.wake_re.config import (
    PINLIST_URL_TEMPLATE,
    VALIDATE_ADDRESS_URL_TEMPLATE,
    ACCOUNT_URL_TEMPLATE,
    PARCEL_ID_LENGTH,
)


def parse_parcel_id(parcel_id: str) -> Optional[dict]:
    """
    Parse 10-digit Wake County parcel ID into components.

    Format: MMMMBBLLLL (4-2-4 split)
        - MMMM: Map number (first 4 digits)
        - BB: Block number (next 2 digits)
        - LLLL: Lot number (last 4 digits)

    Args:
        parcel_id: 10-digit parcel ID like "0753018148"

    Returns:
        {'map': '0753', 'block': '01', 'lot': '8148'} or None if invalid
    """
    if not parcel_id:
        return None

    parcel_id = str(parcel_id).strip()

    if len(parcel_id) != PARCEL_ID_LENGTH:
        return None

    if not parcel_id.isdigit():
        return None

    return {
        'map': parcel_id[0:4],
        'block': parcel_id[4:6],
        'lot': parcel_id[6:10],
    }


def build_pinlist_url(parcel_id: str) -> Optional[str]:
    """
    Build PinList URL from parcel ID.

    Args:
        parcel_id: 10-digit parcel ID

    Returns:
        Full URL or None if parcel ID invalid
    """
    parsed = parse_parcel_id(parcel_id)
    if not parsed:
        return None

    return PINLIST_URL_TEMPLATE.format(**parsed)


def build_validate_address_url(stnum: str, stname: str) -> str:
    """
    Build ValidateAddress URL from address components.

    Args:
        stnum: Street number (e.g., "414")
        stname: Street name without type suffix (e.g., "salem")

    Returns:
        Full URL with URL-encoded parameters
    """
    # URL encode with + for spaces
    encoded_stname = quote_plus(stname.lower())

    return VALIDATE_ADDRESS_URL_TEMPLATE.format(
        stnum=stnum,
        stname=encoded_stname,
    )


def build_account_url(account_id: str) -> str:
    """
    Build final Account.asp URL.

    Args:
        account_id: Wake County account ID (e.g., "0379481")

    Returns:
        Full URL to property account page
    """
    return ACCOUNT_URL_TEMPLATE.format(account_id=account_id)
