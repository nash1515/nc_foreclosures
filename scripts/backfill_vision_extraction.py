#!/usr/bin/env python3
"""
Backfill Vision extraction for existing upset_bid cases.

One-time script to process all documents for cases currently in upset_bid status.
Run after deploying Vision extraction feature.

Usage:
    PYTHONPATH=$(pwd) venv/bin/python scripts/backfill_vision_extraction.py [--dry-run] [--limit N]
"""
import argparse
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import Case, Document
from ocr.vision_extraction import sweep_case_documents, update_case_from_vision_results
from common.logger import setup_logger

logger = setup_logger(__name__)


def backfill_vision_extraction(dry_run: bool = False, limit: int = None):
    """
    Process all upset_bid cases with Vision extraction.

    Args:
        dry_run: If True, only report what would be done
        limit: Max number of cases to process (None = all)
    """
    # Extract case data first to avoid long-lived session
    case_data = []
    with get_session() as session:
        # Get all upset_bid cases
        query = session.query(Case).filter_by(classification='upset_bid')
        if limit:
            query = query.limit(limit)

        cases = query.all()

        logger.info(f"Found {len(cases)} upset_bid cases to check")

        for case in cases:
            # Count unprocessed documents
            unprocessed = session.query(Document).filter(
                Document.case_id == case.id,
                Document.vision_processed_at.is_(None),
                Document.file_path.isnot(None)
            ).count()

            if unprocessed > 0:
                case_data.append({
                    'id': case.id,
                    'case_number': case.case_number,
                    'unprocessed': unprocessed
                })

    if not case_data:
        logger.info("No cases with unprocessed documents found")
        return

    logger.info(f"Processing {len(case_data)} cases with unprocessed documents")

    total_docs = 0
    total_cost = 0.0

    # Process outside session (each sweep_case_documents opens its own session)
    for i, case_info in enumerate(case_data, 1):
        logger.info(
            f"[{i}/{len(case_data)}] {case_info['case_number']}: "
            f"{case_info['unprocessed']} documents to process"
        )

        if dry_run:
            total_docs += case_info['unprocessed']
            # Estimate cost: ~$0.02 per document
            total_cost += case_info['unprocessed'] * 0.02
            continue

        # Process the case (opens its own session internally)
        result = sweep_case_documents(case_info['id'])

        if result['documents_processed'] > 0:
            update_case_from_vision_results(case_info['id'], result['results'])

        total_docs += result['documents_processed']
        total_cost += result['total_cost_cents'] / 100.0

        if result['errors']:
            for err in result['errors']:
                logger.warning(f"    Error: {err}")

        logger.info(
            f"    Processed {result['documents_processed']} docs, "
            f"${result['total_cost_cents']/100:.2f}"
        )

    # Summary
    logger.info("=" * 50)
    if dry_run:
        logger.info(f"DRY RUN - Would process {total_docs} documents")
        logger.info(f"Estimated cost: ${total_cost:.2f}")
    else:
        logger.info(f"Backfill complete: {total_docs} documents processed")
        logger.info(f"Total cost: ${total_cost:.2f}")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill Vision extraction for upset_bid cases'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report what would be done without processing'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of cases to process'
    )

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Vision Extraction Backfill")
    logger.info(f"Started: {datetime.now().isoformat()}")
    if args.dry_run:
        logger.info("MODE: Dry run")
    logger.info("=" * 50)

    backfill_vision_extraction(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
