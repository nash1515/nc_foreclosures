"""Main enricher for Chatham County Real Estate."""

import logging
from datetime import datetime
from typing import Optional

from database.connection import get_session
from database.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment
from enrichments.common.address_parser import parse_address
from enrichments.chatham_re.config import COUNTY_CODE
from enrichments.chatham_re.scraper import search_by_address
from enrichments.chatham_re.url_builder import build_property_url


logger = logging.getLogger(__name__)


class ChathamREEnricher(BaseEnricher):
    """Enricher for Chatham County Real Estate URLs."""

    enrichment_type = 'chatham_re'

    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with Chatham County RE URL.

        Strategy:
            1. Parse address to get street number and name
            2. Search Chatham County DEVNET wEdge portal via HTTP requests
            3. If single match, capture the property URL with parcel ID

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
                    error=f"Case {case.case_number} is not Chatham County (code={case.county_code})"
                )

            logger.info(f"Enriching case {case.case_number} with Chatham RE data")

            # Store case data for processing outside session
            case_number = case.case_number
            property_address = case.property_address

        # Require address for Chatham
        if not property_address:
            error = "No property_address available"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        return self._enrich_by_address(case_id, case_number, property_address)

    def _enrich_by_address(self, case_id: int, case_number: str, property_address: str) -> EnrichmentResult:
        """Enrich using address search via HTTP requests."""
        # Parse address to build search query
        parsed = parse_address(property_address)

        if not parsed.get('stnum') or not parsed.get('name'):
            error = f"Could not parse address: {property_address}"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        street_number = parsed['stnum']
        street_name = parsed['name']  # Just the street name, no prefix
        direction = parsed.get('prefix')  # Directional prefix (N, S, E, W)

        logger.debug(f"Searching Chatham for: {street_number} {direction or ''} {street_name}")

        # Search via HTTP requests
        result = search_by_address(street_number, street_name, direction)

        if result.success and result.parcel_id:
            # Success - single match
            url = result.url or build_property_url(result.parcel_id)
            self._save_success(case_id, url, result.parcel_id)
            return EnrichmentResult(success=True, url=url, account_id=result.parcel_id)

        elif result.matches_found == 0:
            # No matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=0,
                raw_results={
                    'parsed': parsed,
                    'street_number': street_number,
                    'street_name': street_name,
                    'direction': direction,
                    'error': result.error
                },
            )
            return EnrichmentResult(success=False, review_needed=True, error="No matches found")

        elif result.matches_found > 1:
            # Multiple matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=result.matches_found,
                raw_results={
                    'parsed': parsed,
                    'street_number': street_number,
                    'street_name': street_name,
                    'direction': direction,
                    'error': result.error
                },
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
        """Set Chatham RE specific fields."""
        enrichment.chatham_re_url = url
        enrichment.chatham_re_parcel_id = account_id
        enrichment.chatham_re_error = error
        enrichment.chatham_re_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich

    Returns:
        Dict with success status and enrichment data
    """
    enricher = ChathamREEnricher()
    result = enricher.enrich(case_id)
    return result.to_dict()
