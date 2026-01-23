"""Zillow enrichment using external zillow_scraper package."""
import logging
import time
from datetime import datetime
from typing import Optional

from zillow_scraper import lookup, ZillowResult, ZillowError

from database.connection import get_session
from database.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment

logger = logging.getLogger(__name__)

# Rate limiting delay (seconds) before Zillow lookup
ZILLOW_DELAY = 5


class ZillowEnricher(BaseEnricher):
    """Enricher for Zillow property URLs and Zestimates."""

    enrichment_type = 'zillow'

    def enrich(self, case_id: int, force: bool = False) -> EnrichmentResult:
        """
        Enrich a case with Zillow URL and Zestimate.

        Args:
            case_id: Database ID of the case
            force: If True, re-enrich even if already enriched

        Returns:
            EnrichmentResult with success status, URL, and zestimate
        """
        with get_session() as session:
            case = session.get(Case, case_id)
            if not case:
                return EnrichmentResult(success=False, error=f"Case {case_id} not found")

            # Check if already enriched (unless force=True)
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not force and enrichment and enrichment.zillow_url:
                logger.info(f"Case {case.case_number} already has Zillow enrichment, skipping")
                return EnrichmentResult(
                    success=True,
                    url=enrichment.zillow_url,
                    account_id=str(enrichment.zillow_zestimate) if enrichment.zillow_zestimate else None
                )

            logger.info(f"Enriching case {case.case_number} with Zillow data")

            case_number = case.case_number
            property_address = case.property_address

        if not property_address:
            error = "No property_address available"
            logger.warning(f"Case {case_number}: {error}")
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        return self._enrich_by_address(case_id, case_number, property_address)

    def _enrich_by_address(
        self,
        case_id: int,
        case_number: str,
        property_address: str
    ) -> EnrichmentResult:
        """Enrich using zillow_scraper lookup."""
        logger.info(f"Looking up Zillow for: {property_address}")

        # Rate limiting delay
        time.sleep(ZILLOW_DELAY)

        result = lookup(property_address)

        if isinstance(result, ZillowResult):
            # Success
            url = result.url
            zestimate = result.zestimate
            logger.info(f"Case {case_number}: Found Zillow URL, zestimate=${zestimate}")
            self._save_success(case_id, url, zestimate)
            return EnrichmentResult(
                success=True,
                url=url,
                account_id=str(zestimate) if zestimate else None
            )
        else:
            # ZillowError
            error = result.message or result.error
            logger.warning(f"Case {case_number}: Zillow lookup failed - {error}")
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

    def _save_success(self, case_id: int, url: str, zestimate: Optional[int]) -> None:
        """Save successful Zillow enrichment."""
        with get_session() as session:
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not enrichment:
                enrichment = Enrichment(case_id=case_id)
                session.add(enrichment)
            self._set_enrichment_fields(enrichment, url, zestimate, error=None)

    def _save_error(self, case_id: int, error: str) -> None:
        """Save Zillow enrichment error."""
        with get_session() as session:
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not enrichment:
                enrichment = Enrichment(case_id=case_id)
                session.add(enrichment)
            self._set_enrichment_fields(enrichment, url=None, zestimate=None, error=error)

    def _set_enrichment_fields(
        self,
        enrichment: Enrichment,
        url: Optional[str],
        zestimate: Optional[int],
        error: Optional[str]
    ) -> None:
        """Set Zillow specific fields."""
        enrichment.zillow_url = url
        enrichment.zillow_zestimate = zestimate
        enrichment.zillow_error = error
        enrichment.zillow_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int, force: bool = False) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich
        force: If True, re-enrich even if already enriched

    Returns:
        Dict with success status and enrichment data
    """
    enricher = ZillowEnricher()
    result = enricher.enrich(case_id, force=force)
    return result.to_dict()
