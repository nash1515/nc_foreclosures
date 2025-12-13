"""Self-diagnosis and healing for upset_bid cases with missing data."""

from typing import Dict, List, Optional
from database.connection import get_session
from database.models import Case, Document, CaseEvent
from common.logger import setup_logger
from extraction.extractor import update_case_with_extracted_data
from ocr.processor import process_case_documents
from scraper.case_monitor import CaseMonitor

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


def _tier2_reocr(case: Case) -> bool:
    """
    Tier 2: Re-OCR existing documents and extract.

    This tier is for cases where documents exist but OCR may have failed
    or been incomplete. It does NOT re-download documents (that requires
    a browser session - use case_monitor.py for that).

    Args:
        case: Case to heal

    Returns:
        True if OCR was attempted
    """
    logger.info(f"Case {case.case_number}: Tier 2 (re-OCR) - attempting...")
    try:
        # Check if we have documents to process
        with get_session() as session:
            docs = session.query(Document).filter(
                Document.case_id == case.id
            ).all()
            doc_count = len(docs)
            session.expunge_all()

        if doc_count == 0:
            logger.info(f"Case {case.case_number}: Tier 2 - no documents found")
            logger.info(f"  To download documents, run: python scraper/case_monitor.py --case-number {case.case_number}")
            return False

        # Re-OCR the documents
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


def _tier3_rescrape(case: Case) -> bool:
    """
    Tier 3: Full re-scrape via CaseMonitor.

    Args:
        case: Case to heal

    Returns:
        True if re-scrape was attempted
    """
    logger.info(f"Case {case.case_number}: Tier 3 (re-scrape) - attempting...")
    try:
        monitor = CaseMonitor(max_workers=1, headless=False, max_retries=2)
        results = monitor.run(cases=[case])

        logger.info(f"Case {case.case_number}: Tier 3 - re-scrape complete")

        # OCR any new documents
        processed = process_case_documents(case.id)
        if processed:
            logger.info(f"Case {case.case_number}: Tier 3 - processed {processed} new documents")

        # Extract data
        updated = update_case_with_extracted_data(case.id)
        if updated:
            logger.info(f"Case {case.case_number}: Tier 3 - extraction updated case")

        return True
    except Exception as e:
        logger.error(f"Case {case.case_number}: Tier 3 failed - {e}")
        return False
