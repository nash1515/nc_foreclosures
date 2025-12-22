"""Main enricher for Durham County Real Estate."""

import logging
from datetime import datetime
from typing import Optional

from database.connection import get_session
from database.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment
from enrichments.common.address_parser import parse_address
from enrichments.durham_re.config import COUNTY_CODE
from enrichments.durham_re.scraper import search_by_address
from enrichments.durham_re.url_builder import build_property_url


logger = logging.getLogger(__name__)


class DurhamREEnricher(BaseEnricher):
    """Enricher for Durham County Real Estate URLs."""

    enrichment_type = 'durham_re'

    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with Durham County RE URL.

        Strategy:
            1. Parse address to get street number and name
            2. Search Durham CAMA portal via Playwright
            3. If single match, capture the PropertySummary URL

        Args:
            case_id: Database ID of the case

        Returns:
            EnrichmentResult with success status and URL
        """
        # Fetch case
        with get_session() as session:
            case = session.get(Case, case_id)
            if not case:
                return EnrichmentResult(success=False, error=f"Case {case_id} not found")

            if case.county_code != COUNTY_CODE:
                return EnrichmentResult(
                    success=False,
                    error=f"Case {case.case_number} is not Durham County (code={case.county_code})"
                )

            logger.info(f"Enriching case {case.case_number} with Durham RE data")

            # Store case data for processing outside session
            case_number = case.case_number
            property_address = case.property_address

        # Require address for Durham (no parcel ID lookup implemented)
        if not property_address:
            error = "No property_address available"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        return self._enrich_by_address(case_id, case_number, property_address)

    def _enrich_by_address(self, case_id: int, case_number: str, property_address: str) -> EnrichmentResult:
        """Enrich using address search via Playwright."""
        # Parse address
        parsed = parse_address(property_address)

        if not parsed.get('stnum') or not parsed.get('name'):
            error = f"Could not parse address: {property_address}"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        stnum = parsed['stnum']
        street_name = parsed['name']

        # Durham instructions say not to include type or direction
        # The address parser already separates these
        logger.debug(f"Searching Durham for: {stnum} {street_name}")

        # Search via Playwright
        result = search_by_address(stnum, street_name)

        if result.success and result.parcelpk:
            # Success - single match
            url = result.url or build_property_url(result.parcelpk)
            self._save_success(case_id, url, result.parcelpk)
            return EnrichmentResult(success=True, url=url, account_id=result.parcelpk)

        elif result.matches_found == 0:
            # No matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=0,
                raw_results={'parsed': parsed, 'error': result.error},
            )
            return EnrichmentResult(success=False, review_needed=True, error="No matches found")

        elif result.matches_found > 1:
            # Multiple matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=result.matches_found,
                raw_results={'parsed': parsed, 'error': result.error},
            )
            return EnrichmentResult(
                success=False,
                review_needed=True,
                error=f"{result.matches_found} matches found"
            )

        else:
            # Other error (timeout, etc.)
            error = result.error or "Unknown error during search"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

    def _set_enrichment_fields(
        self,
        enrichment: Enrichment,
        url: Optional[str],
        account_id: Optional[str],
        error: Optional[str],
    ) -> None:
        """Set Durham RE specific fields."""
        enrichment.durham_re_url = url
        enrichment.durham_re_parcelpk = account_id
        enrichment.durham_re_error = error
        enrichment.durham_re_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich

    Returns:
        Dict with success status and enrichment data
    """
    enricher = DurhamREEnricher()
    result = enricher.enrich(case_id)
    return result.to_dict()
