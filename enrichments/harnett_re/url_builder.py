"""URL construction for Harnett County Real Estate."""

from enrichments.harnett_re.config import PROPERTY_URL_TEMPLATE


def build_property_url(prid: str) -> str:
    """
    Build the Harnett County AppraisalCard URL.

    Args:
        prid: The property record ID from the Harnett CAMA system

    Returns:
        Full AppraisalCard URL
    """
    return PROPERTY_URL_TEMPLATE.format(prid=prid)


def extract_prid_from_url(url: str) -> str | None:
    """
    Extract prid value from an AppraisalCard URL.

    Args:
        url: Full AppraisalCard URL (e.g., .../AppraisalCard.aspx?prid=8067356)

    Returns:
        prid value or None if not found
    """
    if 'prid=' not in url:
        return None

    try:
        prid = url.split('prid=')[1].split('&')[0]
        return prid
    except (IndexError, AttributeError):
        return None
