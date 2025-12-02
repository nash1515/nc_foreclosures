#!/usr/bin/env python3
"""Re-scrape cases that have NULL event types to get complete data.

Usage:
    PYTHONPATH=$(pwd) venv/bin/python scraper/rescrape_null_events.py [--workers N] [--limit N]
"""

import argparse
from datetime import datetime

from database.connection import get_session
from database.models import Case, CaseEvent
from scraper.case_monitor import CaseMonitor
from common.logger import setup_logger

logger = setup_logger(__name__)


def get_cases_with_null_events(limit: int = None) -> list:
    """Get all cases that have at least one NULL event_type."""
    with get_session() as session:
        # Subquery to find case IDs with NULL events
        null_event_case_ids = session.query(CaseEvent.case_id).filter(
            CaseEvent.event_type.is_(None)
        ).distinct().subquery()

        # Get cases with valid URLs
        query = session.query(Case).filter(
            Case.id.in_(null_event_case_ids),
            Case.case_url.isnot(None)
        )

        if limit:
            query = query.limit(limit)

        cases = query.all()
        session.expunge_all()
        return cases


def main():
    parser = argparse.ArgumentParser(description='Re-scrape cases with NULL event types')
    parser.add_argument('--workers', '-w', type=int, default=4,
                       help='Number of parallel browsers (default: 4)')
    parser.add_argument('--limit', '-l', type=int,
                       help='Maximum number of cases to process')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Max retry attempts per case (default: 3)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without processing')

    args = parser.parse_args()

    # Get cases to process
    cases = get_cases_with_null_events(limit=args.limit)

    logger.info(f"Found {len(cases)} cases with NULL event types")

    if args.dry_run:
        logger.info("[DRY RUN] Would process the following cases:")
        by_classification = {}
        for case in cases:
            cls = case.classification or 'unknown'
            by_classification[cls] = by_classification.get(cls, 0) + 1

        for cls, count in sorted(by_classification.items(), key=lambda x: -x[1]):
            logger.info(f"  {cls}: {count}")
        return

    # Create monitor and run
    monitor = CaseMonitor(
        max_workers=args.workers,
        headless=False,  # Visible browsers for reliability
        max_retries=args.max_retries,
        retry_delay=2.0
    )

    start_time = datetime.now()
    results = monitor.run(cases=cases)
    elapsed = datetime.now() - start_time

    # Summary
    logger.info("=" * 60)
    logger.info("RE-SCRAPE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"  Time elapsed: {elapsed}")
    logger.info(f"  Cases processed: {results['cases_checked']}")
    logger.info(f"  New events added: {results['events_added']}")
    logger.info(f"  Classifications changed: {results['classifications_changed']}")
    logger.info(f"  Errors: {len(results['errors'])}")

    if results['errors']:
        logger.info("\nFailed cases:")
        for error in results['errors'][:20]:  # Show first 20
            logger.info(f"  - {error}")
        if len(results['errors']) > 20:
            logger.info(f"  ... and {len(results['errors']) - 20} more")


if __name__ == '__main__':
    main()
