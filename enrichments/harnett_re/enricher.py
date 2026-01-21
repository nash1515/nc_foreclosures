"""Main enricher for Harnett County Real Estate."""

import logging
from datetime import datetime
from typing import Optional

from database.connection import get_session
from database.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment
from enrichments.common.address_parser import parse_address
from enrichments.harnett_re.config import COUNTY_CODE
from enrichments.harnett_re.scraper import search_by_address
from enrichments.harnett_re.url_builder import build_property_url


logger = logging.getLogger(__name__)


class HarnettREEnricher(BaseEnricher):
    """Enricher for Harnett County Real Estate URLs."""

    enrichment_type = 'harnett_re'

    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with Harnett County RE URL.

        Strategy:
            1. Parse address to get street number and name
            2. Search Harnett CAMA portal via Playwright
            3. If single match, click through and capture the prid URL

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
                    error=f"Case {case.case_number} is not Harnett County (code={case.county_code})"
                )

            logger.info(f"Enriching case {case.case_number} with Harnett RE data")

            # Store case data for processing outside session
            case_number = case.case_number
            property_address = case.property_address

        # Require address for Harnett
        if not property_address:
            error = "No property_address available"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        return self._enrich_by_address(case_id, case_number, property_address)

    def _enrich_by_address(self, case_id: int, case_number: str, property_address: str) -> EnrichmentResult:
        """Enrich using address search via Playwright."""
        # Parse address to build search query
        # Harnett uses a single search field, so we combine stnum + prefix + street name
        parsed = parse_address(property_address)

        if not parsed.get('stnum') or not parsed.get('name'):
            error = f"Could not parse address: {property_address}"
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        # Build search query: "405 E Cole" format (include directional prefix if present)
        if parsed.get('prefix'):
            search_query = f"{parsed['stnum']} {parsed['prefix']} {parsed['name']}"
        else:
            search_query = f"{parsed['stnum']} {parsed['name']}"
        logger.debug(f"Searching Harnett for: {search_query}")

        # Search via Playwright
        result = search_by_address(search_query)

        if result.success and result.prid:
            # Success - single match
            url = result.url or build_property_url(result.prid)
            self._save_success(case_id, url, result.prid)
            return EnrichmentResult(success=True, url=url, account_id=result.prid)

        elif result.matches_found == 0:
            # No matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=0,
                raw_results={'parsed': parsed, 'search_query': search_query, 'error': result.error},
            )
            return EnrichmentResult(success=False, review_needed=True, error="No matches found")

        elif result.matches_found > 1:
            # Multiple matches - log for review
            self._log_review(
                case_id=case_id,
                search_method='address',
                search_value=property_address,
                matches_found=result.matches_found,
                raw_results={'parsed': parsed, 'search_query': search_query, 'error': result.error},
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
        """Set Harnett RE specific fields."""
        enrichment.harnett_re_url = url
        enrichment.harnett_re_prid = account_id
        enrichment.harnett_re_error = error
        enrichment.harnett_re_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich

    Returns:
        Dict with success status and enrichment data
    """
    enricher = HarnettREEnricher()
    result = enricher.enrich(case_id)
    return result.to_dict()
