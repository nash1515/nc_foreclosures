#!/usr/bin/env python3
"""Rescrape all upcoming cases to ensure complete document sets.

This script:
1. Queries all cases with classification='upcoming'
2. For each case, re-downloads ALL documents (skipping existing ones)
3. Designed to run in background with progress logging
4. Does NOT delete existing documents - only adds missing ones

Usage:
    # Rescrape all upcoming cases (safe - won't delete anything)
    python scripts/rescrape_upcoming.py

    # Dry run to see what would be done
    python scripts/rescrape_upcoming.py --dry-run

    # Limit to first N cases (for testing)
    python scripts/rescrape_upcoming.py --limit 10

    # Run with more parallel workers (faster but more resources)
    python scripts/rescrape_upcoming.py --workers 12

    # Run in background and log to file
    nohup python scripts/rescrape_upcoming.py > logs/rescrape_upcoming.log 2>&1 &
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import get_session
from database.models import Case, Document
from scraper.case_monitor import CaseMonitor
from common.logger import setup_logger

logger = setup_logger(__name__)


def get_upcoming_cases(limit: int = None):
    """
    Get all cases with classification='upcoming'.

    Args:
        limit: Optional limit on number of cases to return

    Returns:
        List of Case objects
    """
    with get_session() as session:
        query = session.query(Case).filter(
            Case.classification == 'upcoming',
            Case.case_url.isnot(None)
        ).order_by(Case.file_date.desc())

        if limit:
            query = query.limit(limit)

        cases = query.all()
        session.expunge_all()  # Detach from session

        return cases


def get_case_stats():
    """Get statistics about upcoming cases and their documents."""
    with get_session() as session:
        # Count total upcoming cases
        total_upcoming = session.query(Case).filter(
            Case.classification == 'upcoming'
        ).count()

        # Count cases with no documents
        cases_without_docs = session.query(Case).filter(
            Case.classification == 'upcoming'
        ).outerjoin(Document).filter(
            Document.id.is_(None)
        ).count()

        # Count cases with documents
        cases_with_docs = total_upcoming - cases_without_docs

        return {
            'total_upcoming': total_upcoming,
            'cases_with_docs': cases_with_docs,
            'cases_without_docs': cases_without_docs
        }


def rescrape_upcoming_cases(
    limit: int = None,
    workers: int = 8,
    dry_run: bool = False,
    headless: bool = False
):
    """
    Rescrape all upcoming cases to ensure complete document sets.

    This is a SAFE operation - it only ADDS missing documents, never deletes.

    Args:
        limit: Optional limit on number of cases to process
        workers: Number of parallel browser instances
        dry_run: If True, just show what would be done
        headless: Run browsers in headless mode (default: False for reliability)

    Returns:
        Dict with results
    """
    logger.info("=" * 70)
    logger.info("RESCRAPING UPCOMING CASES FOR COMPLETE DOCUMENT SETS")
    logger.info("=" * 70)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Get statistics
    stats = get_case_stats()
    logger.info(f"\nCase Statistics:")
    logger.info(f"  Total upcoming cases: {stats['total_upcoming']}")
    logger.info(f"  Cases with documents: {stats['cases_with_docs']}")
    logger.info(f"  Cases without documents: {stats['cases_without_docs']}")

    # Get cases to process
    cases = get_upcoming_cases(limit=limit)
    logger.info(f"\nCases to process: {len(cases)}")

    if limit:
        logger.info(f"  (Limited to first {limit} cases)")

    if dry_run:
        logger.info("\n[DRY RUN] Would process the following:")
        logger.info(f"  Total cases: {len(cases)}")
        logger.info(f"  Parallel workers: {workers}")
        logger.info(f"  Headless mode: {headless}")
        logger.info("\nSample cases:")

        for i, case in enumerate(cases[:5]):
            with get_session() as session:
                doc_count = session.query(Document).filter_by(case_id=case.id).count()

            logger.info(f"  {i+1}. {case.case_number} ({case.county_name}) - {doc_count} docs")

        if len(cases) > 5:
            logger.info(f"  ... and {len(cases) - 5} more cases")

        return {'dry_run': True, 'cases_found': len(cases)}

    # Create monitor instance
    logger.info(f"\nInitializing CaseMonitor with {workers} parallel workers...")
    monitor = CaseMonitor(
        max_workers=workers,
        headless=headless,
        max_retries=3,
        retry_delay=2.0
    )

    # Run the monitor
    # The monitor will use download_all_case_documents() which has skip_existing=True
    # This means it will only download documents that aren't already in the database
    logger.info("\nStarting document download process...")
    logger.info("(This may take a while - documents are downloaded in parallel)")

    results = monitor.run(cases=cases, dry_run=False)

    # Final summary
    logger.info("\n" + "=" * 70)
    logger.info("RESCRAPE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"\nResults:")
    logger.info(f"  Cases processed: {results.get('cases_checked', 0)}")
    logger.info(f"  New events added: {results.get('events_added', 0)}")
    logger.info(f"  Classifications changed: {results.get('classifications_changed', 0)}")
    logger.info(f"  Bid updates: {results.get('bid_updates', 0)}")

    if results.get('errors'):
        logger.info(f"  Errors encountered: {len(results['errors'])}")
        logger.info("\nError details:")
        for error in results['errors'][:10]:  # Show first 10 errors
            logger.error(f"  - {error}")
        if len(results['errors']) > 10:
            logger.error(f"  ... and {len(results['errors']) - 10} more errors")
    else:
        logger.info(f"  Errors: 0")

    # Get updated statistics
    final_stats = get_case_stats()
    logger.info(f"\nFinal Statistics:")
    logger.info(f"  Cases with documents: {final_stats['cases_with_docs']} "
               f"(+{final_stats['cases_with_docs'] - stats['cases_with_docs']})")
    logger.info(f"  Cases without documents: {final_stats['cases_without_docs']} "
               f"(-{stats['cases_without_docs'] - final_stats['cases_without_docs']})")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Rescrape all upcoming cases to ensure complete document sets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script is SAFE - it only ADDS missing documents, never deletes existing ones.

Examples:
  # Rescrape all upcoming cases
  python scripts/rescrape_upcoming.py

  # Test with first 10 cases
  python scripts/rescrape_upcoming.py --limit 10

  # Preview what would be done
  python scripts/rescrape_upcoming.py --dry-run

  # Run with more workers (faster)
  python scripts/rescrape_upcoming.py --workers 12

  # Run in background with logging
  nohup python scripts/rescrape_upcoming.py > logs/rescrape_upcoming.log 2>&1 &

Notes:
  - VPN may be required (check with: ./scripts/vpn_status.sh)
  - Uses skip_existing=True so won't re-download files already in DB
  - Safe to run multiple times - idempotent
  - Takes ~1-2 seconds per case on average
        """
    )

    parser.add_argument('--limit', '-l', type=int,
                       help='Limit to first N cases (for testing)')
    parser.add_argument('--workers', '-w', type=int, default=8,
                       help='Number of parallel browser instances (default: 8)')
    parser.add_argument('--headless', action='store_true',
                       help='Run browsers in headless mode (default: visible)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually doing it')

    args = parser.parse_args()

    # Environment check
    if 'PYTHONPATH' not in os.environ:
        logger.warning("PYTHONPATH not set - this may cause import issues")
        logger.warning("Run: export PYTHONPATH=$(pwd)")

    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    # Run the rescrape
    results = rescrape_upcoming_cases(
        limit=args.limit,
        workers=args.workers,
        dry_run=args.dry_run,
        headless=args.headless
    )

    # Exit with error code if there were errors
    if results.get('errors'):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
