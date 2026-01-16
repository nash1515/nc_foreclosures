"""Main enricher for PropWire property data."""

import logging
from datetime import datetime
from typing import Optional

from database.connection import get_session
from database.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment
from enrichments.prop_wire.scraper import search_by_address

logger = logging.getLogger(__name__)


class PropWireEnricher(BaseEnricher):
    """Enricher for PropWire property URLs."""

    enrichment_type = 'propwire'

    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with PropWire property URL.

        Strategy:
            1. Get property address from case
            2. Search PropWire via Playwright autocomplete
            3. If single match, save property URL

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

            logger.info(f"Enriching case {case.case_number} with PropWire data")

            # Store case data for processing outside session
            case_number = case.case_number
            property_address = case.property_address

        # Require address for PropWire search
        if not property_address:
            error = "No property_address available"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        return self._enrich_by_address(case_id, case_number, property_address)

    def _enrich_by_address(
        self,
        case_id: int,
        case_number: str,
        property_address: str
    ) -> EnrichmentResult:
        """Enrich using address search via PropWire autocomplete."""
        # Search via Playwright autocomplete
        result = search_by_address(property_address)

        if result.success and result.property_id:
            # Success - single match
            url = result.url
            self._save_success(case_id, url, result.property_id)
            return EnrichmentResult(
                success=True,
                url=url,
                account_id=result.property_id
            )

        elif result.matches_found == 0:
            # No matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=0,
                raw_results={'error': result.error}
            )
            return EnrichmentResult(
                success=False,
                review_needed=True,
                error="No property found"
            )

        elif result.matches_found > 1:
            # Multiple matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=result.matches_found,
                raw_results={'error': result.error}
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
        error: Optional[str]
    ) -> None:
        """Set PropWire specific fields."""
        enrichment.propwire_url = url
        # PropWire doesn't have a separate account_id field, just the property_id in URL
        enrichment.propwire_error = error
        enrichment.propwire_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich

    Returns:
        Dict with success status and enrichment data
    """
    enricher = PropWireEnricher()
    result = enricher.enrich(case_id)
    return result.to_dict()
