"""
County-based enrichment router.

Routes enrichment requests to the appropriate county-specific enricher
based on the case's county code.
"""

import logging
from database.models import Case
from database.connection import get_session

logger = logging.getLogger(__name__)

# County code to enricher module mapping
# Each county has its own GIS/Real Estate portal with different URL structures
COUNTY_ENRICHERS = {
    '910': 'wake_re',      # Wake County
    '310': 'durham_re',    # Durham County (not implemented)
    '410': 'harnett_re',   # Harnett County (not implemented)
    '530': 'lee_re',       # Lee County (not implemented)
    '680': 'orange_re',    # Orange County (not implemented)
    '180': 'chatham_re',   # Chatham County (not implemented)
}

# Counties with implemented enrichers
IMPLEMENTED_COUNTIES = {'910'}  # Only Wake for now


def get_county_code(case_id: int) -> str | None:
    """Extract county code from case."""
    with get_session() as session:
        case = session.get(Case, case_id)
        if not case:
            return None
        # County code is the last 3 digits of case_number (e.g., 25SP001234-910 -> 910)
        if case.case_number and '-' in case.case_number:
            return case.case_number.split('-')[-1]
        return None


def enrich_case(case_id: int) -> dict:
    """
    Route enrichment to the appropriate county enricher.

    Args:
        case_id: Database ID of the case to enrich

    Returns:
        dict with keys:
            - success: bool
            - url: str (if successful)
            - error: str (if failed)
            - review_needed: bool (if manual review required)
            - skipped: bool (if county not implemented)
    """
    county_code = get_county_code(case_id)

    if not county_code:
        logger.error(f"Could not determine county code for case_id={case_id}")
        return {'success': False, 'error': 'Could not determine county code'}

    if county_code not in COUNTY_ENRICHERS:
        logger.warning(f"Unknown county code {county_code} for case_id={case_id}")
        return {'success': False, 'error': f'Unknown county code: {county_code}'}

    if county_code not in IMPLEMENTED_COUNTIES:
        enricher_name = COUNTY_ENRICHERS[county_code]
        logger.debug(f"Enricher {enricher_name} not implemented for county {county_code}")
        return {'success': False, 'skipped': True, 'error': f'Enricher not implemented: {enricher_name}'}

    # Route to the appropriate enricher
    if county_code == '910':
        from enrichments.wake_re import enrich_case as wake_enrich
        return wake_enrich(case_id)

    # This shouldn't happen if IMPLEMENTED_COUNTIES is kept in sync
    return {'success': False, 'error': f'Enricher routing error for county {county_code}'}
