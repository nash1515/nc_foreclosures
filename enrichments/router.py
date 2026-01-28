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
    '310': 'durham_re',    # Durham County
    '420': 'harnett_re',   # Harnett County
    '520': 'lee_re',       # Lee County
    '670': 'orange_re',    # Orange County
    '180': 'chatham_re',   # Chatham County
}

# Counties with implemented enrichers
IMPLEMENTED_COUNTIES = {'910', '310', '420', '520', '670', '180'}  # Wake, Durham, Harnett, Lee, Orange, Chatham


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
            - county_re: dict (county-specific enrichment result)
            - zillow: dict (Zillow enrichment result)
    """
    county_code = get_county_code(case_id)

    # County RE enrichment
    county_result = None
    if not county_code:
        logger.error(f"Could not determine county code for case_id={case_id}")
        county_result = {'success': False, 'error': 'Could not determine county code'}
    elif county_code not in COUNTY_ENRICHERS:
        logger.warning(f"Unknown county code {county_code} for case_id={case_id}")
        county_result = {'success': False, 'error': f'Unknown county code: {county_code}'}
    elif county_code not in IMPLEMENTED_COUNTIES:
        enricher_name = COUNTY_ENRICHERS[county_code]
        logger.debug(f"Enricher {enricher_name} not implemented for county {county_code}")
        county_result = {'success': False, 'skipped': True, 'error': f'Enricher not implemented: {enricher_name}'}
    else:
        # Route to the appropriate enricher
        if county_code == '910':
            from enrichments.wake_re import enrich_case as wake_enrich
            county_result = wake_enrich(case_id)
        elif county_code == '310':
            from enrichments.durham_re import enrich_case as durham_enrich
            county_result = durham_enrich(case_id)
        elif county_code == '420':
            from enrichments.harnett_re import enrich_case as harnett_enrich
            county_result = harnett_enrich(case_id)
        elif county_code == '520':
            from enrichments.lee_re import enrich_case as lee_enrich
            county_result = lee_enrich(case_id)
        elif county_code == '670':
            from enrichments.orange_re import enrich_case as orange_enrich
            county_result = orange_enrich(case_id)
        elif county_code == '180':
            from enrichments.chatham_re import enrich_case as chatham_enrich
            county_result = chatham_enrich(case_id)
        else:
            # This shouldn't happen if IMPLEMENTED_COUNTIES is kept in sync
            county_result = {'success': False, 'error': f'Enricher routing error for county {county_code}'}

    # Zillow enrichment (runs for ALL counties)
    from enrichments.zillow.enricher import enrich_case as zillow_enrich
    zillow_result = zillow_enrich(case_id)

    return {
        'county_re': county_result,
        'zillow': zillow_result,
    }
