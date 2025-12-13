"""Self-diagnosis and healing for upset_bid cases with missing data."""

from typing import Dict, List, Optional
from database.connection import get_session
from database.models import Case, Document, CaseEvent
from common.logger import setup_logger
from extraction.extractor import update_case_with_extracted_data
from ocr.processor import process_case_documents
from scraper.document_downloader import download_case_documents

logger = setup_logger(__name__)

REQUIRED_FIELDS = [
    'case_number',
    'property_address',
    'current_bid_amount',
    'minimum_next_bid',
    'next_bid_deadline',
    'sale_date'
]


def _check_completeness(case: Case) -> List[str]:
    """
    Check which required fields are missing from a case.

    Args:
        case: Case object to check

    Returns:
        List of missing field names (empty if complete)
    """
    missing = []
    for field in REQUIRED_FIELDS:
        value = getattr(case, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def _get_upset_bid_cases() -> List[Case]:
    """Get all upset_bid cases from database."""
    with get_session() as session:
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid'
        ).all()
        session.expunge_all()
        return cases


def _tier1_reextract(case: Case) -> bool:
    """
    Tier 1: Re-run extraction on existing documents.

    Args:
        case: Case to heal

    Returns:
        True if extraction was attempted
    """
    logger.info(f"Case {case.case_number}: Tier 1 (re-extract) - attempting...")
    try:
        updated = update_case_with_extracted_data(case.id)
        if updated:
            logger.info(f"Case {case.case_number}: Tier 1 - extraction updated case")
        else:
            logger.info(f"Case {case.case_number}: Tier 1 - no new data extracted")
        return True
    except Exception as e:
        logger.error(f"Case {case.case_number}: Tier 1 failed - {e}")
        return False


def _tier2_redownload(case: Case) -> bool:
    """
    Tier 2: Re-download documents and extract.

    Args:
        case: Case to heal

    Returns:
        True if download was attempted
    """
    logger.info(f"Case {case.case_number}: Tier 2 (re-download) - attempting...")
    try:
        # Get events with document URLs
        with get_session() as session:
            events = session.query(CaseEvent).filter(
                CaseEvent.case_id == case.id,
                CaseEvent.document_url.isnot(None)
            ).all()
            event_count = len(events)
            session.expunge_all()

        if event_count == 0:
            logger.info(f"Case {case.case_number}: Tier 2 - no document URLs found")
            return False

        # Re-download documents
        downloaded = download_case_documents(case.id, force=True)
        logger.info(f"Case {case.case_number}: Tier 2 - downloaded {downloaded} documents")

        # OCR the documents
        processed = process_case_documents(case.id)
        logger.info(f"Case {case.case_number}: Tier 2 - processed {processed} documents")

        # Re-extract
        updated = update_case_with_extracted_data(case.id)
        if updated:
            logger.info(f"Case {case.case_number}: Tier 2 - extraction updated case")

        return True
    except Exception as e:
        logger.error(f"Case {case.case_number}: Tier 2 failed - {e}")
        return False
