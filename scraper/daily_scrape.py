"""Daily scrape orchestrator - coordinates all daily tasks.

This script runs the complete daily scraping workflow:
1. Search for new cases filed yesterday (or 3 days back on Mondays to catch weekend filings)
2. OCR and extraction for newly downloaded documents
3. Monitor upcoming cases for sale events
4. Monitor blocked cases for status changes
5. Monitor upset_bid cases for new bids or blocking events
6. Reclassify stale cases based on time (upset_bid -> closed_sold)

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
from datetime import datetime, timedelta, timezone, time
from typing import Dict, Optional

from database.connection import get_session
from database.models import Case, ScrapeLog, ScrapeLogTask
from scraper.date_range_scrape import DateRangeScraper
from scraper.case_monitor import CaseMonitor, monitor_cases
from extraction.classifier import reclassify_stale_cases
from scraper.self_diagnosis import diagnose_and_heal_upset_bids
from analysis.queue_processor import process_analysis_queue
from common.logger import setup_logger

logger = setup_logger(__name__)


class TaskLogger:
    """Helper to log task-level details to scrape_log_tasks table."""

    def __init__(self, scrape_log_id: Optional[int] = None):
        self.scrape_log_id = scrape_log_id
        self.task_order = 0

    def start_task(self, task_name: str) -> Optional[int]:
        """Create a task entry and return its ID."""
        if not self.scrape_log_id:
            return None
        self.task_order += 1
        with get_session() as session:
            task = ScrapeLogTask(
                scrape_log_id=self.scrape_log_id,
                task_name=task_name,
                task_order=self.task_order,
                status='in_progress'
            )
            session.add(task)
            session.commit()
            return task.id

    def complete_task(self, task_id: Optional[int], status: str = 'success',
                      items_checked: int = None, items_found: int = None,
                      items_processed: int = None, error_message: str = None):
        """Update task with completion details."""
        if not task_id:
            return
        with get_session() as session:
            task = session.query(ScrapeLogTask).filter_by(id=task_id).first()
            if task:
                task.status = status
                task.completed_at = datetime.now()
                if items_checked is not None:
                    task.items_checked = items_checked
                if items_found is not None:
                    task.items_found = items_found
                if items_processed is not None:
                    task.items_processed = items_processed
                if error_message:
                    task.error_message = error_message
                session.commit()

    def log_completed_task(self, task_name: str, started_at: datetime, completed_at: datetime,
                           status: str = 'success', items_checked: int = None,
                           items_found: int = None, items_processed: int = None,
                           error_message: str = None) -> Optional[int]:
        """Log a task that has already completed with explicit timestamps."""
        if not self.scrape_log_id:
            return None
        self.task_order += 1
        with get_session() as session:
            task = ScrapeLogTask(
                scrape_log_id=self.scrape_log_id,
                task_name=task_name,
                task_order=self.task_order,
                started_at=started_at,
                completed_at=completed_at,
                status=status,
                items_checked=items_checked,
                items_found=items_found,
                items_processed=items_processed,
                error_message=error_message
            )
            session.add(task)
            session.commit()
            return task.id

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


def validate_upset_bid_data(dry_run: bool = False) -> Dict:
    """
    Validate that all upset_bid cases have required bid data.

    This catches cases that were classified as upset_bid but are missing:
    - current_bid_amount
    - next_bid_deadline

    These cases need their documents re-downloaded and re-processed.

    Args:
        dry_run: If True, only report issues without taking action

    Returns:
        Dict with validation results
    """
    logger.info("=" * 60)
    logger.info("TASK: Validate upset_bid data completeness")
    logger.info("=" * 60)

    results = {
        'missing_bid_amount': [],
        'missing_deadline': [],
        'missing_both': [],
        'total_issues': 0,
    }

    with get_session() as session:
        # Find upset_bid cases missing bid amount
        missing_bid = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.current_bid_amount.is_(None)
        ).all()

        # Find upset_bid cases missing deadline
        missing_deadline = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.next_bid_deadline.is_(None)
        ).all()

        # Categorize
        missing_bid_ids = {c.id for c in missing_bid}
        missing_deadline_ids = {c.id for c in missing_deadline}

        both = missing_bid_ids & missing_deadline_ids
        only_bid = missing_bid_ids - both
        only_deadline = missing_deadline_ids - both

        for case in missing_bid:
            case_info = {
                'id': case.id,
                'case_number': case.case_number,
                'county': case.case_number.split('-')[-1] if '-' in case.case_number else 'unknown'
            }

            if case.id in both:
                results['missing_both'].append(case_info)
                logger.warning(f"  Case {case.case_number}: missing BOTH bid amount AND deadline")
            elif case.id in only_bid:
                results['missing_bid_amount'].append(case_info)
                logger.warning(f"  Case {case.case_number}: missing bid amount (has deadline: {case.next_bid_deadline})")

        for case in missing_deadline:
            if case.id in only_deadline:
                case_info = {
                    'id': case.id,
                    'case_number': case.case_number,
                    'county': case.case_number.split('-')[-1] if '-' in case.case_number else 'unknown'
                }
                results['missing_deadline'].append(case_info)
                logger.warning(f"  Case {case.case_number}: missing deadline (has bid: ${case.current_bid_amount})")

    results['total_issues'] = (
        len(results['missing_both']) +
        len(results['missing_bid_amount']) +
        len(results['missing_deadline'])
    )

    if results['total_issues'] == 0:
        logger.info("All upset_bid cases have complete bid data")
    else:
        logger.warning(f"Found {results['total_issues']} upset_bid cases with incomplete data:")
        logger.warning(f"  - Missing both: {len(results['missing_both'])}")
        logger.warning(f"  - Missing bid only: {len(results['missing_bid_amount'])}")
        logger.warning(f"  - Missing deadline only: {len(results['missing_deadline'])}")

        if not dry_run:
            # Return the case IDs for remediation
            all_problem_ids = (
                [c['id'] for c in results['missing_both']] +
                [c['id'] for c in results['missing_bid_amount']] +
                [c['id'] for c in results['missing_deadline']]
            )
            results['problem_case_ids'] = all_problem_ids
            logger.info(f"Problem case IDs: {all_problem_ids}")

    return results


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
    # Deadline expires at 5 PM courthouse close, not midnight
    # Only consider cases stale if: deadline date < today OR (deadline date = today AND current time > 5 PM)
    with get_session() as session:
        now = datetime.now()
        today = now.date()
        past_5pm_today = now.hour >= 17

        # Get all upset_bid cases with deadlines
        stale_cases = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.next_bid_deadline != None
        ).all()

        # Filter to truly stale cases (deadline passed)
        stale_count = 0
        for case in stale_cases:
            deadline_date = case.next_bid_deadline.date()
            if deadline_date < today:
                stale_count += 1
            elif deadline_date == today and past_5pm_today:
                stale_count += 1

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

    # Default to yesterday, but on Mondays look back 3 days to catch Friday filings
    if target_date is None:
        now = datetime.now(timezone.utc)
        # Monday is 0, Sunday is 6
        if now.weekday() == 0:
            # Monday: look back 3 days (to Friday)
            lookback_days = 3
            logger.info("Monday detected - looking back 3 days to catch weekend filings")
        else:
            # Other weekdays: look back 1 day
            lookback_days = 1

        target_date = (now - timedelta(days=lookback_days)).date()
        logger.info(f"Using {lookback_days}-day lookback period")

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
        'ocr_processed': None,
        'case_monitoring': None,
        'upset_bid_validation': None,
        'stale_reclassification': None,
        'self_diagnosis': None,
        'errors': []
    }

    # Task logger - will be initialized once we have a scrape_log_id
    task_logger = TaskLogger()

    # Task 1: Search for new cases
    if search_new:
        task1_start = datetime.now()
        try:
            results['new_case_search'] = run_new_case_search(target_date, dry_run)
            task1_end = datetime.now()
            # Get scrape_log_id from the search result to log subsequent tasks
            scrape_log_id = results['new_case_search'].get('scrape_log_id')
            if scrape_log_id:
                task_logger.scrape_log_id = scrape_log_id
                # Log Task 1 with actual timestamps
                task_logger.log_completed_task(
                    'new_case_search',
                    started_at=task1_start,
                    completed_at=task1_end,
                    status='success' if not results['new_case_search'].get('error') else 'failed',
                    items_found=results['new_case_search'].get('cases_processed', 0),
                    items_processed=results['new_case_search'].get('cases_processed', 0)
                )
        except Exception as e:
            logger.error(f"Task 1 failed: {e}")
            results['errors'].append(f"new_case_search: {e}")

    # Task 1.5: OCR and extraction for newly downloaded documents
    if search_new and not dry_run:
        task_id = task_logger.start_task('ocr_after_search')
        try:
            logger.info("=" * 60)
            logger.info("TASK 1.5: OCR and extraction for new documents")
            logger.info("=" * 60)

            from ocr.processor import process_unprocessed_documents
            ocr_count = process_unprocessed_documents()

            results['ocr_processed'] = ocr_count
            logger.info(f"OCR processed {ocr_count} documents (extraction auto-triggered)")
            task_logger.complete_task(task_id, items_processed=ocr_count)
        except Exception as e:
            logger.error(f"Task 1.5 failed: {e}")
            results['errors'].append(f"ocr_processing: {e}")
            task_logger.complete_task(task_id, status='failed', error_message=str(e))

    # Task 2: Monitor existing cases
    if monitor_existing:
        task_id = task_logger.start_task('case_monitoring')
        try:
            results['case_monitoring'] = run_case_monitoring(dry_run)
            task_logger.complete_task(
                task_id,
                items_checked=results['case_monitoring'].get('cases_checked', 0),
                items_found=results['case_monitoring'].get('events_added', 0),
                items_processed=results['case_monitoring'].get('classifications_changed', 0)
            )
        except Exception as e:
            logger.error(f"Task 2 failed: {e}")
            results['errors'].append(f"case_monitoring: {e}")
            task_logger.complete_task(task_id, status='failed', error_message=str(e))

    # Task 2.5: OCR documents downloaded during monitoring
    if monitor_existing and not dry_run:
        task_id = task_logger.start_task('ocr_after_monitoring')
        try:
            from ocr.processor import process_unprocessed_documents
            ocr_count = process_unprocessed_documents()
            if ocr_count > 0:
                logger.info(f"OCR processed {ocr_count} documents from monitoring")
                if results.get('ocr_processed'):
                    results['ocr_processed'] += ocr_count
                else:
                    results['ocr_processed'] = ocr_count
            task_logger.complete_task(task_id, items_processed=ocr_count)
        except Exception as e:
            logger.error(f"Task 2.5 failed: {e}")
            results['errors'].append(f"ocr_processing_monitoring: {e}")
            task_logger.complete_task(task_id, status='failed', error_message=str(e))

    # Task 3: Validate upset_bid data completeness (always run)
    task_id = task_logger.start_task('upset_bid_validation')
    try:
        results['upset_bid_validation'] = validate_upset_bid_data(dry_run)
        task_logger.complete_task(
            task_id,
            items_checked=results['upset_bid_validation'].get('total_upset_bid', 0),
            items_found=results['upset_bid_validation'].get('total_issues', 0)
        )
    except Exception as e:
        logger.error(f"Task 3 failed: {e}")
        results['errors'].append(f"upset_bid_validation: {e}")
        task_logger.complete_task(task_id, status='failed', error_message=str(e))

    # Task 4: Reclassify stale cases (always run)
    task_id = task_logger.start_task('stale_reclassification')
    try:
        results['stale_reclassification'] = run_stale_reclassification(dry_run)
        task_logger.complete_task(
            task_id,
            items_checked=results['stale_reclassification'].get('stale_count', 0),
            items_processed=results['stale_reclassification'].get('reclassified', 0)
        )
    except Exception as e:
        logger.error(f"Task 4 failed: {e}")
        results['errors'].append(f"stale_reclassification: {e}")
        task_logger.complete_task(task_id, status='failed', error_message=str(e))

    # Task 5: Self-diagnosis and healing
    logger.info("=" * 60)
    logger.info("TASK 5: Self-diagnosis for upset_bid cases")
    logger.info("=" * 60)
    task_id = task_logger.start_task('self_diagnosis')
    try:
        results['self_diagnosis'] = diagnose_and_heal_upset_bids(dry_run)
        diag = results['self_diagnosis']
        task_logger.complete_task(
            task_id,
            items_checked=diag.get('cases_checked', 0),
            items_found=diag.get('cases_incomplete', 0),
            items_processed=diag.get('cases_healed', 0)
        )
    except Exception as e:
        logger.error(f"Task 5 (self-diagnosis) failed: {e}")
        results['errors'].append(f"self_diagnosis: {e}")
        results['self_diagnosis'] = {'error': str(e)}
        task_logger.complete_task(task_id, status='failed', error_message=str(e))

    # Task 6: Process AI Analysis Queue
    task_id = task_logger.start_task('ai_analysis_queue')
    try:
        logger.info("Task 6: Processing AI analysis queue")
        analysis_result = process_analysis_queue(max_items=10)
        task_logger.complete_task(
            task_id,
            items_checked=analysis_result['processed'],
            items_processed=analysis_result['succeeded']
        )
        logger.info(f"Task 6 complete: {analysis_result['succeeded']}/{analysis_result['processed']} analyses completed")
    except Exception as e:
        logger.error(f"Task 6 failed: {e}")
        results['errors'].append(f"ai_analysis_queue: {e}")
        task_logger.complete_task(task_id, status='failed', error_message=str(e))

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

    if results.get('ocr_processed') is not None:
        ocr_count = results.get('ocr_processed', 0)
        logger.info(f"Documents OCR processed: {ocr_count} (extraction auto-triggered)")

    if results['case_monitoring']:
        monitored = results['case_monitoring'].get('cases_checked', 0)
        events_added = results['case_monitoring'].get('events_added', 0)
        classifications_changed = results['case_monitoring'].get('classifications_changed', 0)
        logger.info(f"Cases monitored: {monitored}")
        logger.info(f"New events found: {events_added}")
        logger.info(f"Classifications changed: {classifications_changed}")

    if results['upset_bid_validation']:
        issues = results['upset_bid_validation'].get('total_issues', 0)
        if issues > 0:
            logger.warning(f"Upset bid data issues found: {issues} cases need attention")
        else:
            logger.info(f"Upset bid data validation: PASSED (all cases have complete data)")

    if results['stale_reclassification']:
        reclassified = results['stale_reclassification'].get('reclassified', 0)
        logger.info(f"Stale cases reclassified: {reclassified}")

    if results['self_diagnosis']:
        diag = results['self_diagnosis']
        if 'error' in diag:
            logger.error(f"Self-diagnosis failed: {diag['error']}")
        else:
            checked = diag.get('cases_checked', 0)
            incomplete = diag.get('cases_incomplete', 0)
            healed = diag.get('cases_healed', 0)
            unresolved = len(diag.get('cases_unresolved', []))
            if incomplete == 0:
                logger.info(f"Self-diagnosis: All {checked} upset_bid cases complete")
            else:
                logger.info(f"Self-diagnosis: {incomplete} incomplete, {healed} healed, {unresolved} unresolved")

    if results['errors']:
        logger.warning(f"Errors: {len(results['errors'])}")
        for error in results['errors']:
            logger.warning(f"  - {error}")

    results['end_time'] = str(end_time)
    results['duration_seconds'] = duration.total_seconds()

    # Update the scrape_log's completed_at to reflect the full workflow duration
    # (not just Task 1's completion time which was set by DateRangeScraper)
    if task_logger.scrape_log_id:
        with get_session() as session:
            log = session.query(ScrapeLog).get(task_logger.scrape_log_id)
            if log:
                log.completed_at = end_time
                session.commit()
                logger.debug(f"Updated scrape_log {task_logger.scrape_log_id} completed_at to {end_time}")

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
