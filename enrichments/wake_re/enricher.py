"""Main enricher for Wake County Real Estate."""

import logging
from datetime import datetime
from typing import Optional

from database.connection import get_session
from database.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment
from enrichments.common.address_parser import parse_address
from enrichments.wake_re.config import ETJ_CODES, COUNTY_CODE
from enrichments.wake_re.url_builder import build_account_url, parse_parcel_id
from enrichments.wake_re.scraper import (
    fetch_pinlist_results,
    fetch_validate_address_results,
    match_address_result,
)


logger = logging.getLogger(__name__)


class WakeREEnricher(BaseEnricher):
    """Enricher for Wake County Real Estate URLs."""

    enrichment_type = 'wake_re'

    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with Wake County RE URL.

        Strategy:
            1. Try parcel ID lookup if available
            2. Fall back to address search
            3. Log ambiguous cases for review

        Args:
            case_id: Database ID of the case

        Returns:
            EnrichmentResult with success status and URL
        """
        # Fetch case
        with get_session() as session:
            case = session.query(Case).get(case_id)
            if not case:
                return EnrichmentResult(success=False, error=f"Case {case_id} not found")

            if case.county_code != COUNTY_CODE:
                return EnrichmentResult(
                    success=False,
                    error=f"Case {case.case_number} is not Wake County (code={case.county_code})"
                )

            logger.info(f"Enriching case {case.case_number} with Wake RE data")

            # Store case data for processing outside session
            case_number = case.case_number
            parcel_id = case.parcel_id
            property_address = case.property_address

        # Try parcel ID first
        if parcel_id and parse_parcel_id(parcel_id):
            result = self._enrich_by_parcel_id(case_id, case_number, parcel_id)
            if result.success or result.review_needed:
                return result
            # If parcel ID failed (not review), fall through to address
            logger.info(f"Parcel ID lookup failed for {case_number}, trying address")

        # Fall back to address
        if property_address:
            return self._enrich_by_address(case_id, case_number, property_address)

        # No parcel ID or address
        error = "No parcel_id or property_address available"
        self._save_error(case_id, error)
        return EnrichmentResult(success=False, error=error)

    def _enrich_by_parcel_id(self, case_id: int, case_number: str, parcel_id: str) -> EnrichmentResult:
        """Enrich using parcel ID lookup."""
        try:
            results = fetch_pinlist_results(parcel_id)
        except Exception as e:
            error = f"PinList fetch error: {e}"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        if len(results) == 1:
            # Success - single match
            account_id = results[0]['account_id']
            url = build_account_url(account_id)
            self._save_success(case_id, url, account_id)
            return EnrichmentResult(success=True, url=url, account_id=account_id)

        elif len(results) == 0:
            # No matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='parcel_id',
                search_value=parcel_id,
                matches_found=0,
                raw_results={'results': results},
            )
            return EnrichmentResult(success=False, review_needed=True, error="No matches found")

        else:
            # Multiple matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='parcel_id',
                search_value=parcel_id,
                matches_found=len(results),
                raw_results={'results': results},
            )
            return EnrichmentResult(success=False, review_needed=True, error=f"{len(results)} matches found")

    def _enrich_by_address(self, case_id: int, case_number: str, property_address: str) -> EnrichmentResult:
        """Enrich using address search."""
        # Parse address
        parsed = parse_address(property_address)

        if not parsed.get('stnum') or not parsed.get('name'):
            error = f"Could not parse address: {property_address}"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        # Fetch address search results
        try:
            results = fetch_validate_address_results(parsed['stnum'], parsed['name'])
        except Exception as e:
            error = f"Address search error: {e}"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        # Get ETJ code for city matching
        etj = None
        if parsed.get('city'):
            etj = ETJ_CODES.get(parsed['city'].lower())

        # Try to find single match
        match = match_address_result(
            results,
            stnum=parsed['stnum'],
            prefix=parsed['prefix'],
            name=parsed['name'],
            etj=etj,
        )

        if match:
            account_id = match['account_id']
            url = build_account_url(account_id)
            self._save_success(case_id, url, account_id)
            return EnrichmentResult(success=True, url=url, account_id=account_id)

        # No single match - determine reason and log
        matches_count = len(results) if results else 0
        self._log_review(
            case_id=case_id,
            search_method='address',
            search_value=property_address,
            matches_found=matches_count,
            raw_results={'parsed': parsed, 'results': results},
        )
        return EnrichmentResult(
            success=False,
            review_needed=True,
            error=f"{matches_count} matches found for address"
        )

    def _set_enrichment_fields(
        self,
        enrichment: Enrichment,
        url: Optional[str],
        account_id: Optional[str],
        error: Optional[str],
    ) -> None:
        """Set Wake RE specific fields."""
        enrichment.wake_re_url = url
        enrichment.wake_re_account = account_id
        enrichment.wake_re_error = error
        enrichment.wake_re_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich

    Returns:
        Dict with success status and enrichment data
    """
    enricher = WakeREEnricher()
    result = enricher.enrich(case_id)
    return result.to_dict()
