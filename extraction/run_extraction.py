#!/usr/bin/env python3
"""CLI script for running data extraction on cases.

Usage:
    # Process all cases with OCR text
    PYTHONPATH=$(pwd) python extraction/run_extraction.py

    # Process specific case
    PYTHONPATH=$(pwd) python extraction/run_extraction.py --case-id 123

    # Only classify (skip extraction)
    PYTHONPATH=$(pwd) python extraction/run_extraction.py --classify-only

    # Only extract (skip classification)
    PYTHONPATH=$(pwd) python extraction/run_extraction.py --extract-only

    # Reprocess all cases (even if already extracted)
    PYTHONPATH=$(pwd) python extraction/run_extraction.py --reprocess

    # Limit for testing
    PYTHONPATH=$(pwd) python extraction/run_extraction.py --limit 10
"""

import argparse
import sys

from extraction.extractor import (
    update_case_with_extracted_data,
    process_unextracted_cases,
    extract_all_from_case
)
from extraction.classifier import (
    update_case_classification,
    classify_all_cases,
    reclassify_stale_cases
)
from database.connection import get_session
from database.models import Case, Document
from common.logger import setup_logger

logger = setup_logger(__name__)


def process_single_case(case_id: int, extract: bool = True, classify: bool = True):
    """Process a single case."""
    logger.info(f"Processing case {case_id}...")

    if extract:
        logger.info("  Running extraction...")
        extracted = extract_all_from_case(case_id)

        # Log what was found
        for key, value in extracted.items():
            if value:
                if key == 'legal_description' and len(str(value)) > 50:
                    logger.info(f"    {key}: {str(value)[:50]}...")
                else:
                    logger.info(f"    {key}: {value}")

        # Update database
        update_case_with_extracted_data(case_id)

    if classify:
        logger.info("  Running classification...")
        classification = update_case_classification(case_id)
        logger.info(f"    classification: {classification}")


def process_all_cases(limit: int = None, extract: bool = True, classify: bool = True, reprocess: bool = False):
    """Process all cases."""
    logger.info("=" * 60)
    logger.info("EXTRACTION PROCESSING")
    logger.info("=" * 60)

    # Get case IDs and numbers (not full objects) to avoid session issues
    case_info = []
    with get_session() as session:
        if reprocess:
            # Get all cases with OCR text
            query = session.query(Case.id, Case.case_number).join(Document).filter(
                Document.ocr_text.isnot(None)
            ).distinct()
        else:
            # Get cases that haven't been extracted yet
            query = session.query(Case.id, Case.case_number).join(Document).filter(
                Document.ocr_text.isnot(None),
                Case.property_address.is_(None)  # Proxy for "not yet extracted"
            ).distinct()

        if limit:
            query = query.limit(limit)

        case_info = [(c.id, c.case_number) for c in query.all()]

    total = len(case_info)
    logger.info(f"Found {total} cases to process")

    if total == 0:
        logger.info("No cases need processing")
        return

    extracted_count = 0
    classified_count = 0

    for i, (case_id, case_number) in enumerate(case_info, 1):
        logger.info(f"\n[{i}/{total}] Case {case_number} (ID: {case_id})")

        if extract:
            if update_case_with_extracted_data(case_id):
                extracted_count += 1

        if classify:
            if update_case_classification(case_id):
                classified_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("EXTRACTION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Cases processed: {total}")
    if extract:
        logger.info(f"Cases with extracted data: {extracted_count}")
    if classify:
        logger.info(f"Cases classified: {classified_count}")
    logger.info("=" * 60)


def show_case_data(case_id: int):
    """Show all data for a case."""
    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            logger.error(f"Case {case_id} not found")
            return

        logger.info(f"\nCase {case.case_number}:")
        logger.info(f"  County: {case.county_name}")
        logger.info(f"  Type: {case.case_type}")
        logger.info(f"  Status: {case.case_status}")
        logger.info(f"  Style: {case.style}")
        logger.info(f"  File Date: {case.file_date}")
        logger.info(f"  Property Address: {case.property_address}")
        logger.info(f"  Current Bid: {case.current_bid_amount}")
        logger.info(f"  Bid Deadline: {case.next_bid_deadline}")
        logger.info(f"  Sale Date: {case.sale_date}")
        logger.info(f"  Classification: {case.classification}")
        logger.info(f"  Trustee: {case.trustee_name}")
        logger.info(f"  Attorney: {case.attorney_name}")
        logger.info(f"  Attorney Phone: {case.attorney_phone}")
        logger.info(f"  Attorney Email: {case.attorney_email}")

        if case.legal_description:
            desc = case.legal_description[:100] + "..." if len(case.legal_description) > 100 else case.legal_description
            logger.info(f"  Legal Desc: {desc}")


def main():
    parser = argparse.ArgumentParser(description='NC Foreclosures Data Extraction')

    parser.add_argument('--case-id', type=int, help='Process a specific case')
    parser.add_argument('--classify-only', action='store_true', help='Only run classification')
    parser.add_argument('--extract-only', action='store_true', help='Only run extraction')
    parser.add_argument('--reprocess', action='store_true', help='Reprocess cases with existing data')
    parser.add_argument('--limit', type=int, help='Limit number of cases to process')
    parser.add_argument('--show', type=int, metavar='CASE_ID', help='Show all data for a case')
    parser.add_argument('--reclassify-stale', action='store_true',
                       help='Re-classify cases that may have changed status')

    args = parser.parse_args()

    # Determine what to run
    extract = not args.classify_only
    classify = not args.extract_only

    if args.show:
        show_case_data(args.show)
    elif args.reclassify_stale:
        logger.info("Re-classifying stale cases...")
        count = reclassify_stale_cases()
        logger.info(f"Reclassified {count} cases")
    elif args.case_id:
        process_single_case(args.case_id, extract=extract, classify=classify)
    else:
        process_all_cases(
            limit=args.limit,
            extract=extract,
            classify=classify,
            reprocess=args.reprocess
        )


if __name__ == '__main__':
    main()
