"""
Deed enrichment router.

Routes deed URL generation to county-specific builders based on case number suffix.
"""

import logging
from datetime import datetime

from database.connection import get_session
from database.models import Case
from enrichments.common.models import Enrichment
from enrichments.deed.url_builders import (
    build_wake_url,
    build_durham_url,
    build_harnett_url,
    build_orange_url,
    build_lee_url,
    build_chatham_url,
)

logger = logging.getLogger(__name__)

# County codes
COUNTY_CODES = {
    '910': 'Wake',
    '310': 'Durham',
    '420': 'Harnett',
    '520': 'Lee',
    '670': 'Orange',
    '180': 'Chatham',
}


def build_deed_url(case_number: str, deed_book: str, deed_page: str) -> str | None:
    """
    Build deed URL for the given case.

    Args:
        case_number: Case number with county suffix (e.g., "25SP001234-910")
        deed_book: Deed book number from AI extraction
        deed_page: Deed page number from AI extraction

    Returns:
        URL string or None if inputs invalid
    """
    if not deed_book or not deed_page:
        return None

    if '-' not in case_number:
        logger.warning(f"Invalid case number format: {case_number}")
        return None

    county_code = case_number.split('-')[-1]

    if county_code == '910':  # Wake
        return build_wake_url(deed_book, deed_page)
    elif county_code == '310':  # Durham - search page only
        return build_durham_url()
    elif county_code == '420':  # Harnett
        return build_harnett_url(deed_book, deed_page)
    elif county_code == '520':  # Lee - search page only
        return build_lee_url()
    elif county_code == '670':  # Orange
        return build_orange_url(deed_book, deed_page)
    elif county_code == '180':  # Chatham - search page only
        return build_chatham_url()
    else:
        logger.warning(f"Unknown county code: {county_code}")
        return None


def enrich_deed(case_id: int, deed_book: str, deed_page: str) -> dict:
    """
    Generate and store deed URL for a case.

    Args:
        case_id: Database case ID
        deed_book: Deed book number
        deed_page: Deed page number

    Returns:
        dict with success status and url or error
    """
    with get_session() as session:
        case = session.get(Case, case_id)
        if not case:
            return {'success': False, 'error': 'Case not found'}

        # Build URL
        url = build_deed_url(case.case_number, deed_book, deed_page)
        if not url:
            return {'success': False, 'error': 'Could not build deed URL'}

        # Get or create enrichment record
        enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
        if not enrichment:
            enrichment = Enrichment(case_id=case_id)
            session.add(enrichment)

        # Store URL
        enrichment.deed_url = url
        enrichment.deed_enriched_at = datetime.now()
        enrichment.deed_error = None

        session.commit()
        logger.info(f"Deed enrichment complete for case_id={case_id}: {url}")

        return {'success': True, 'url': url}
