#!/usr/bin/env python3
"""
Reprocess a case - nuclear reset that re-extracts all data from all documents.

Usage:
    python scripts/reprocess_case.py <case_number>
    python scripts/reprocess_case.py --case-id <id>
    python scripts/reprocess_case.py --all-upset-bid  # Reprocess all upset_bid cases
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import Case, CaseEvent, Document
from extraction.extractor import update_case_with_extracted_data
from common.logger import setup_logger

logger = setup_logger(__name__)


def reprocess_case(case_id: int, clear_address: bool = True) -> bool:
    """
    Reprocess a case - clear extracted fields and re-extract from all documents.

    Args:
        case_id: ID of case to reprocess
        clear_address: If True, clear property_address (default True for full reset)

    Returns:
        True if successful
    """
    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            logger.error(f"Case ID {case_id} not found")
            return False

        logger.info(f"Reprocessing case {case.case_number} (ID: {case_id})")

        # Clear extracted fields for full re-extraction
        if clear_address:
            old_address = case.property_address
            case.property_address = None
            logger.info(f"  Cleared address: {old_address}")

        # Note: We don't clear bid amounts - those should come from events
        # Note: We don't clear sale_date - that's event-derived

        # Clear extraction_attempted_at on all documents to force re-OCR if needed
        docs_cleared = session.query(Document)\
            .filter(Document.case_id == case_id)\
            .update({Document.extraction_attempted_at: None})
        logger.info(f"  Reset extraction flag on {docs_cleared} documents")

        session.commit()

    # Run full extraction (event_ids=None means all documents)
    logger.info(f"  Running full extraction...")
    result = update_case_with_extracted_data(case_id, event_ids=None)

    if result:
        logger.info(f"  Reprocess complete - data updated")
    else:
        logger.info(f"  Reprocess complete - no changes")

    return True


def main():
    parser = argparse.ArgumentParser(description='Reprocess a case (full re-extraction)')
    parser.add_argument('case_number', nargs='?', help='Case number (e.g., 24-CVS-1234)')
    parser.add_argument('--case-id', type=int, help='Case ID (database primary key)')
    parser.add_argument('--all-upset-bid', action='store_true',
                        help='Reprocess all upset_bid cases')
    parser.add_argument('--keep-address', action='store_true',
                        help='Keep existing address (only re-extract other fields)')

    args = parser.parse_args()

    if args.all_upset_bid:
        with get_session() as session:
            cases = session.query(Case).filter_by(classification='upset_bid').all()
            logger.info(f"Reprocessing {len(cases)} upset_bid cases...")
            for case in cases:
                reprocess_case(case.id, clear_address=not args.keep_address)
    elif args.case_id:
        reprocess_case(args.case_id, clear_address=not args.keep_address)
    elif args.case_number:
        with get_session() as session:
            case = session.query(Case).filter_by(case_number=args.case_number).first()
            if not case:
                logger.error(f"Case {args.case_number} not found")
                sys.exit(1)
            reprocess_case(case.id, clear_address=not args.keep_address)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
