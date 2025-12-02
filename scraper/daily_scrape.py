"""Daily scrape orchestrator - coordinates all daily tasks.

This script runs the complete daily scraping workflow:
1. Search for new cases filed yesterday (or specified date)
2. Monitor upcoming cases for sale events
3. Monitor blocked cases for status changes
4. Monitor upset_bid cases for new bids or blocking events
5. Reclassify stale cases based on time (upset_bid -> closed_sold)

Usage:
    # Run all daily tasks
    PYTHONPATH=$(pwd) venv/bin/python scraper/daily_scrape.py

    # Search only (skip monitoring)
    PYTHONPATH=$(pwd) venv/bin/python scraper/daily_scrape.py --search-only

    # Monitor only (skip new case search)
    PYTHONPATH=$(pwd) venv/bin/python scraper/daily_scrape.py --monitor-only

    # Dry run
    PYTHONPATH=$(pwd) venv/bin/python scraper/daily_scrape.py --dry-run

    # Specific date for new case search
    PYTHONPATH=$(pwd) venv/bin/python scraper/daily_scrape.py --date 2025-11-30

Cron example (run at 6 AM daily):
    0 6 * * * /home/ahn/projects/nc_foreclosures/scripts/run_daily.sh >> /home/ahn/projects/nc_foreclosures/logs/daily.log 2>&1
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from database.connection import get_session
from database.models import Case
from scraper.date_range_scrape import DateRangeScraper
from scraper.case_monitor import CaseMonitor, monitor_cases
from extraction.classifier import reclassify_stale_cases
from common.logger import setup_logger

logger = setup_logger(__name__)

# Target counties
TARGET_COUNTIES = ['wake', 'durham', 'orange', 'chatham', 'lee', 'harnett']


def get_case_counts() -> Dict[str, int]:
    """Get current case counts by classification."""
    with get_session() as session:
        results = session.query(
            Case.classification,
            session.query(Case).filter(Case.classification == Case.classification).count()
        ).group_by(Case.classification).all()

        counts = {}
        for classification, count in session.execute(
            "SELECT classification, COUNT(*) FROM cases GROUP BY classification"
        ).fetchall():
            counts[classification or 'unclassified'] = count

        return counts


def run_new_case_search(target_date: datetime.date, dry_run: bool = False) -> Dict:
    """
    Search for new cases filed on target date.

    Args:
        target_date: Date to search for new cases
        dry_run: If True, show what would be done

    Returns:
        Dict with search results
    """
    logger.info("=" * 60)
    logger.info(f"TASK 1: Search for new cases - {target_date}")
    logger.info("=" * 60)

    if dry_run:
        logger.info(f"[DRY RUN] Would search for cases filed on {target_date}")
        logger.info(f"[DRY RUN] Counties: {', '.join(TARGET_COUNTIES)}")
        return {'dry_run': True, 'target_date': str(target_date)}

    try:
        scraper = DateRangeScraper(
            start_date=target_date.strftime('%Y-%m-%d'),
            end_date=target_date.strftime('%Y-%m-%d'),
            counties=TARGET_COUNTIES
        )
        result = scraper.run()

        logger.info(f"New cases found: {result.get('cases_processed', 0)}")
        return result

    except Exception as e:
        logger.error(f"New case search failed: {e}")
        return {'error': str(e), 'cases_processed': 0}


def run_case_monitoring(dry_run: bool = False) -> Dict:
    """
    Monitor existing cases for status changes.

    Args:
        dry_run: If True, show what would be done

    Returns:
        Dict with monitoring results
    """
    logger.info("=" * 60)
    logger.info("TASK 2: Monitor existing cases")
    logger.info("=" * 60)

    # Get counts before monitoring
    with get_session() as session:
        upcoming_count = session.query(Case).filter(Case.classification == 'upcoming').count()
        blocked_count = session.query(Case).filter(Case.classification == 'blocked').count()
        upset_bid_count = session.query(Case).filter(Case.classification == 'upset_bid').count()

    logger.info(f"Cases to monitor:")
    logger.info(f"  - upcoming: {upcoming_count}")
    logger.info(f"  - blocked: {blocked_count}")
    logger.info(f"  - upset_bid: {upset_bid_count}")
    logger.info(f"  - TOTAL: {upcoming_count + blocked_count + upset_bid_count}")

    if dry_run:
        logger.info("[DRY RUN] Would monitor all cases listed above")
        return {
            'dry_run': True,
            'upcoming': upcoming_count,
            'blocked': blocked_count,
            'upset_bid': upset_bid_count
        }

    try:
        results = monitor_cases(dry_run=False)
        return results

    except Exception as e:
        logger.error(f"Case monitoring failed: {e}")
        return {'error': str(e)}


def run_stale_reclassification(dry_run: bool = False) -> Dict:
    """
    Reclassify cases that have become stale due to time passing.

    This handles upset_bid cases where the deadline has passed.

    Args:
        dry_run: If True, show what would be done

    Returns:
        Dict with reclassification results
    """
    logger.info("=" * 60)
    logger.info("TASK 3: Reclassify stale cases")
    logger.info("=" * 60)

    # Check for upset_bid cases with passed deadlines
    with get_session() as session:
        now = datetime.now()
        stale_count = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.next_bid_deadline < now
        ).count()

    logger.info(f"Stale upset_bid cases (deadline passed): {stale_count}")

    if dry_run:
        logger.info("[DRY RUN] Would reclassify stale cases")
        return {'dry_run': True, 'stale_count': stale_count}

    if stale_count == 0:
        logger.info("No stale cases to reclassify")
        return {'reclassified': 0}

    try:
        reclassified = reclassify_stale_cases()
        logger.info(f"Reclassified {reclassified} cases")
        return {'reclassified': reclassified}

    except Exception as e:
        logger.error(f"Stale reclassification failed: {e}")
        return {'error': str(e)}


def run_daily_tasks(
    target_date: Optional[datetime.date] = None,
    search_new: bool = True,
    monitor_existing: bool = True,
    dry_run: bool = False
) -> Dict:
    """
    Run all daily tasks.

    Args:
        target_date: Date for new case search (default: yesterday)
        search_new: Whether to search for new cases
        monitor_existing: Whether to monitor existing cases
        dry_run: If True, show what would be done

    Returns:
        Dict with all results
    """
    start_time = datetime.now()

    # Default to yesterday
    if target_date is None:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    logger.info("=" * 60)
    logger.info("DAILY SCRAPE STARTED")
    logger.info("=" * 60)
    logger.info(f"Start time: {start_time}")
    logger.info(f"Target date for new cases: {target_date}")
    logger.info(f"Search new cases: {search_new}")
    logger.info(f"Monitor existing: {monitor_existing}")
    logger.info(f"Dry run: {dry_run}")

    results = {
        'start_time': str(start_time),
        'target_date': str(target_date),
        'new_case_search': None,
        'case_monitoring': None,
        'stale_reclassification': None,
        'errors': []
    }

    # Task 1: Search for new cases
    if search_new:
        try:
            results['new_case_search'] = run_new_case_search(target_date, dry_run)
        except Exception as e:
            logger.error(f"Task 1 failed: {e}")
            results['errors'].append(f"new_case_search: {e}")

    # Task 2: Monitor existing cases
    if monitor_existing:
        try:
            results['case_monitoring'] = run_case_monitoring(dry_run)
        except Exception as e:
            logger.error(f"Task 2 failed: {e}")
            results['errors'].append(f"case_monitoring: {e}")

    # Task 3: Reclassify stale cases (always run)
    try:
        results['stale_reclassification'] = run_stale_reclassification(dry_run)
    except Exception as e:
        logger.error(f"Task 3 failed: {e}")
        results['errors'].append(f"stale_reclassification: {e}")

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    logger.info("")
    logger.info("=" * 60)
    logger.info("DAILY SCRAPE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Duration: {duration}")

    if results['new_case_search']:
        new_cases = results['new_case_search'].get('cases_processed', 0)
        logger.info(f"New cases added: {new_cases}")

    if results['case_monitoring']:
        monitored = results['case_monitoring'].get('cases_checked', 0)
        events_added = results['case_monitoring'].get('events_added', 0)
        classifications_changed = results['case_monitoring'].get('classifications_changed', 0)
        logger.info(f"Cases monitored: {monitored}")
        logger.info(f"New events found: {events_added}")
        logger.info(f"Classifications changed: {classifications_changed}")

    if results['stale_reclassification']:
        reclassified = results['stale_reclassification'].get('reclassified', 0)
        logger.info(f"Stale cases reclassified: {reclassified}")

    if results['errors']:
        logger.warning(f"Errors: {len(results['errors'])}")
        for error in results['errors']:
            logger.warning(f"  - {error}")

    results['end_time'] = str(end_time)
    results['duration_seconds'] = duration.total_seconds()

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Daily scrape orchestrator for NC foreclosures',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all daily tasks
  python scraper/daily_scrape.py

  # Search only (skip monitoring)
  python scraper/daily_scrape.py --search-only

  # Monitor only (skip new case search)
  python scraper/daily_scrape.py --monitor-only

  # Dry run
  python scraper/daily_scrape.py --dry-run

  # Specific date for new case search
  python scraper/daily_scrape.py --date 2025-11-30
"""
    )

    parser.add_argument(
        '--date',
        help='Date to search for new cases (YYYY-MM-DD). Default: yesterday'
    )
    parser.add_argument(
        '--search-only',
        action='store_true',
        help='Only search for new cases, skip monitoring'
    )
    parser.add_argument(
        '--monitor-only',
        action='store_true',
        help='Only monitor existing cases, skip new case search'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    # Determine target date
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)

    # Determine what to run
    search_new = not args.monitor_only
    monitor_existing = not args.search_only

    if args.search_only and args.monitor_only:
        logger.error("Cannot specify both --search-only and --monitor-only")
        sys.exit(1)

    # Run the daily tasks
    results = run_daily_tasks(
        target_date=target_date,
        search_new=search_new,
        monitor_existing=monitor_existing,
        dry_run=args.dry_run
    )

    # Exit with error code if there were errors
    if results['errors']:
        sys.exit(1)

    sys.exit(0)


if __name__ == '__main__':
    main()
