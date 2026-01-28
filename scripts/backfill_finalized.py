#!/usr/bin/env python3
"""
Backfill is_finalized flag for cases that have finalization events.

This script:
1. Finds all cases that have finalization events (Order Confirming Sale, Final Report, etc.)
2. Marks them as finalized (is_finalized=True, finalized_at=now(), finalized_event_id)
3. Reports results

Finalization events indicate the case is truly complete - funds disbursed, all accounts settled.
These are stronger indicators than just "Order Confirming Sale" which happens after upset period.

Usage:
    python scripts/backfill_finalized.py
    python scripts/backfill_finalized.py --dry-run
    python scripts/backfill_finalized.py --limit 10
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from database.connection import get_session
from database.models import Case, CaseEvent
from extraction.classifier import (
    get_case_events,
    has_finalization_event,
    get_finalization_event,
    FINALIZATION_EVENTS
)
from common.logger import setup_logger

logger = setup_logger(__name__)


def backfill_finalized_cases(dry_run: bool = False, limit: int = None) -> dict:
    """
    Find cases with finalization events and mark them as finalized.

    Args:
        dry_run: If True, only report what would be changed
        limit: Maximum number of cases to process

    Returns:
        Dict with statistics
    """
    stats = {
        'total_checked': 0,
        'already_finalized': 0,
        'newly_finalized': 0,
        'no_finalization_event': 0,
        'errors': 0
    }

    # Get all cases
    with get_session() as session:
        query = session.query(Case)

        if limit:
            query = query.limit(limit)

        # Extract data before session closes
        case_data = []
        for case in query.all():
            case_data.append({
                'id': case.id,
                'case_number': case.case_number,
                'is_finalized': case.is_finalized,
                'finalized_at': case.finalized_at,
                'finalized_event_id': case.finalized_event_id
            })

    logger.info(f"Found {len(case_data)} cases to check")
    logger.info(f"Looking for finalization events: {', '.join(FINALIZATION_EVENTS)}")

    if dry_run:
        logger.info("DRY RUN MODE - no changes will be made")

    # Process each case
    for i, case_dict in enumerate(case_data, 1):
        case_id = case_dict['id']
        case_number = case_dict['case_number']

        if i % 100 == 0:
            logger.info(f"Progress: {i}/{len(case_data)} cases checked")

        stats['total_checked'] += 1

        try:
            # Skip if already finalized
            if case_dict['is_finalized']:
                stats['already_finalized'] += 1
                logger.debug(f"  {case_number}: Already finalized (event_id={case_dict['finalized_event_id']})")
                continue

            # Get events for this case
            events = get_case_events(case_id)

            # Check if has finalization event
            if not has_finalization_event(events):
                stats['no_finalization_event'] += 1
                logger.debug(f"  {case_number}: No finalization event found")
                continue

            # Get the finalization event
            finalization_event = get_finalization_event(events)

            if not finalization_event:
                logger.warning(f"  {case_number}: has_finalization_event() returned True but get_finalization_event() returned None")
                stats['errors'] += 1
                continue

            # Mark as finalized
            if dry_run:
                logger.info(f"  {case_number}: WOULD mark as finalized (event: {finalization_event.event_type}, date: {finalization_event.event_date})")
                stats['newly_finalized'] += 1
            else:
                with get_session() as session:
                    case = session.query(Case).filter_by(id=case_id).first()
                    if case:
                        case.is_finalized = True
                        case.finalized_at = datetime.now()
                        case.finalized_event_id = finalization_event.id
                        session.commit()
                        logger.info(f"  {case_number}: Marked as finalized (event: {finalization_event.event_type}, date: {finalization_event.event_date})")
                        stats['newly_finalized'] += 1
                    else:
                        logger.error(f"  {case_number}: Case not found in database")
                        stats['errors'] += 1

        except Exception as e:
            logger.error(f"  {case_number}: Error processing case: {e}")
            stats['errors'] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description='Backfill is_finalized flag for cases with finalization events')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of cases to process')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("BACKFILL FINALIZED CASES")
    logger.info("=" * 80)

    stats = backfill_finalized_cases(dry_run=args.dry_run, limit=args.limit)

    # Print summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total cases checked:         {stats['total_checked']}")
    logger.info(f"Already finalized:           {stats['already_finalized']}")
    logger.info(f"Newly finalized:             {stats['newly_finalized']}")
    logger.info(f"No finalization event:       {stats['no_finalization_event']}")
    logger.info(f"Errors:                      {stats['errors']}")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("")
        logger.info("This was a DRY RUN - no changes were made")
        logger.info("Run without --dry-run to apply changes")


if __name__ == '__main__':
    main()
