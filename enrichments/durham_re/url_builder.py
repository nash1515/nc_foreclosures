"""URL construction for Durham County Real Estate."""

from enrichments.durham_re.config import PROPERTY_URL_TEMPLATE


def build_property_url(parcelpk: str) -> str:
    """
    Build the Durham County PropertySummary URL.

    Args:
        parcelpk: The PARCELPK value from the Durham CAMA system

    Returns:
        Full PropertySummary URL
    """
    return PROPERTY_URL_TEMPLATE.format(parcelpk=parcelpk)


def extract_parcelpk_from_url(url: str) -> str | None:
    """
    Extract PARCELPK value from a PropertySummary URL.

    Args:
        url: Full PropertySummary URL

    Returns:
        PARCELPK value or None if not found
    """
    if 'PARCELPK=' not in url:
        return None

    try:
        # Extract value after PARCELPK=
        parcelpk = url.split('PARCELPK=')[1].split('&')[0]
        return parcelpk
    except (IndexError, AttributeError):
        return None
