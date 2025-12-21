"""Abstract base class for enrichment modules."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

from database.connection import get_session
from enrichments.common.models import Enrichment, EnrichmentReviewLog


logger = logging.getLogger(__name__)


class EnrichmentResult:
    """Result object for enrichment operations."""

    def __init__(
        self,
        success: bool,
        url: Optional[str] = None,
        account_id: Optional[str] = None,
        error: Optional[str] = None,
        review_needed: bool = False,
    ):
        self.success = success
        self.url = url
        self.account_id = account_id
        self.error = error
        self.review_needed = review_needed

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'url': self.url,
            'account_id': self.account_id,
            'error': self.error,
            'review_needed': self.review_needed,
        }


class BaseEnricher(ABC):
    """Abstract base class for all enrichment modules."""

    # Subclasses must define these
    enrichment_type: str = None  # e.g., 'wake_re', 'durham_re'

    @abstractmethod
    def enrich(self, case_id: int) -> EnrichmentResult:
        """
        Enrich a case with external data.

        Args:
            case_id: Database ID of the case to enrich

        Returns:
            EnrichmentResult with success status and data
        """
        pass

    @abstractmethod
    def _set_enrichment_fields(
        self,
        enrichment: Enrichment,
        url: Optional[str],
        account_id: Optional[str],
        error: Optional[str],
    ) -> None:
        """
        Set enrichment-type-specific fields on the enrichment record.

        Subclasses must implement to set their specific columns.

        Args:
            enrichment: Enrichment record to update
            url: URL to the external resource (None if error)
            account_id: External account/reference ID (None if error)
            error: Error message (None if success)
        """
        pass

    def _log_review(
        self,
        case_id: int,
        search_method: str,
        search_value: str,
        matches_found: int,
        raw_results: dict,
    ) -> EnrichmentReviewLog:
        """
        Log cases needing manual review to enrichment_review_log.

        Args:
            case_id: Case database ID
            search_method: 'parcel_id' or 'address'
            search_value: The value used for search
            matches_found: Number of matches (0 or 2+)
            raw_results: Raw search results for debugging

        Returns:
            Created review log entry
        """
        with get_session() as session:
            log = EnrichmentReviewLog(
                case_id=case_id,
                enrichment_type=self.enrichment_type,
                search_method=search_method,
                search_value=search_value,
                matches_found=matches_found,
                raw_results=raw_results,
            )
            session.add(log)
            # Commit handled by context manager

        logger.warning(
            f"Case {case_id}: {matches_found} matches for {search_method}='{search_value}' - logged for review"
        )

        return log

    def _save_success(
        self,
        case_id: int,
        url: str,
        account_id: str,
    ) -> None:
        """
        Save successful enrichment result.

        Args:
            case_id: Case database ID
            url: URL to the external resource
            account_id: External account/reference ID
        """
        with get_session() as session:
            # Get or create enrichment record
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not enrichment:
                enrichment = Enrichment(case_id=case_id)
                session.add(enrichment)

            # Set type-specific fields (subclass implements)
            self._set_enrichment_fields(enrichment, url, account_id, error=None)
            # Commit handled by context manager

        logger.info(f"Case {case_id}: {self.enrichment_type} enrichment succeeded - {url}")

    def _save_error(
        self,
        case_id: int,
        error: str,
    ) -> None:
        """
        Save enrichment error.

        Args:
            case_id: Case database ID
            error: Error message
        """
        with get_session() as session:
            # Get or create enrichment record
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not enrichment:
                enrichment = Enrichment(case_id=case_id)
                session.add(enrichment)

            self._set_enrichment_fields(enrichment, url=None, account_id=None, error=error)
            # Commit handled by context manager

        logger.error(f"Case {case_id}: {self.enrichment_type} enrichment failed - {error}")
