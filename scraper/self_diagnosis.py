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


def diagnose_and_heal_upset_bids(dry_run: bool = False) -> Dict:
    """
    Check all upset_bid cases for completeness and attempt self-healing.

    Args:
        dry_run: If True, only check completeness without healing

    Returns:
        Dict with diagnosis results
    """
    results = {
        'cases_checked': 0,
        'cases_incomplete': 0,
        'cases_healed': 0,
        'cases_unresolved': [],
        'healing_attempts': {
            'tier1_reextract': {'attempted': 0, 'succeeded': 0},
            'tier2_reocr': {'attempted': 0, 'succeeded': 0},
            'tier3_rescrape': {'attempted': 0, 'succeeded': 0}
        }
    }

    cases = _get_upset_bid_cases()
    results['cases_checked'] = len(cases)
    logger.info(f"Self-diagnosis: checking {len(cases)} upset_bid cases")

    for case in cases:
        missing = _check_completeness(case)

        if not missing:
            continue  # Already complete

        results['cases_incomplete'] += 1
        logger.info(f"Case {case.case_number}: missing {missing}")

        if dry_run:
            results['cases_unresolved'].append({
                'case_id': case.id,
                'case_number': case.case_number,
                'missing_fields': missing
            })
            continue

        # Tier 1: Re-extract
        results['healing_attempts']['tier1_reextract']['attempted'] += 1
        _tier1_reextract(case)

        # Refresh case and check
        with get_session() as session:
            refreshed = session.query(Case).filter_by(id=case.id).first()
            missing = _check_completeness(refreshed)
            session.expunge(refreshed)

        if not missing:
            results['healing_attempts']['tier1_reextract']['succeeded'] += 1
            results['cases_healed'] += 1
            logger.info(f"Case {case.case_number}: Tier 1 - complete, all fields populated")
            continue

        # Tier 2: Re-OCR
        results['healing_attempts']['tier2_reocr']['attempted'] += 1
        _tier2_reocr(case)

        with get_session() as session:
            refreshed = session.query(Case).filter_by(id=case.id).first()
            missing = _check_completeness(refreshed)
            session.expunge(refreshed)

        if not missing:
            results['healing_attempts']['tier2_reocr']['succeeded'] += 1
            results['cases_healed'] += 1
            logger.info(f"Case {case.case_number}: Tier 2 - complete, all fields populated")
            continue

        # Tier 3: Full re-scrape
        results['healing_attempts']['tier3_rescrape']['attempted'] += 1
        _tier3_rescrape(case)

        with get_session() as session:
            refreshed = session.query(Case).filter_by(id=case.id).first()
            missing = _check_completeness(refreshed)
            session.expunge(refreshed)

        if not missing:
            results['healing_attempts']['tier3_rescrape']['succeeded'] += 1
            results['cases_healed'] += 1
            logger.info(f"Case {case.case_number}: Tier 3 - complete, all fields populated")
            continue

        # Still incomplete after all tiers
        results['cases_unresolved'].append({
            'case_id': case.id,
            'case_number': case.case_number,
            'missing_fields': missing
        })
        logger.warning(f"Case {case.case_number}: unresolved after all tiers, missing {missing}")

    healed = results['cases_healed']
    unresolved = len(results['cases_unresolved'])
    logger.info(f"Self-diagnosis complete: {results['cases_incomplete']} incomplete, {healed} healed, {unresolved} unresolved")

    return results
