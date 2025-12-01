"""Parallel batch scrape - runs all counties simultaneously.

Each county gets its own browser instance running in parallel.
Failures are tracked to a JSON file for later retry.

Usage:
    # Year mode (uses monthly/quarterly splits per county)
    python scraper/parallel_batch_scrape.py --year 2024
    python scraper/parallel_batch_scrape.py --year 2024 --retry-failures
    python scraper/parallel_batch_scrape.py --year 2024 --dry-run

    # Date range mode (same range for all counties - good for catch-up/daily scrapes)
    python scraper/parallel_batch_scrape.py --start 2025-11-27 --end 2025-11-30
    python scraper/parallel_batch_scrape.py --start 2025-11-27 --end 2025-11-30 --county wake
"""

import argparse
import json
import sys
import os
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scraper.initial_scrape import InitialScraper, TruncatedResultsError
from scraper.date_range_scrape import run_date_range_scrape as run_single_search_scrape
from scraper.vpn_manager import verify_vpn_or_exit
from common.logger import setup_logger
from common.config import config

logger = setup_logger(__name__)

# Counties and their search strategies
COUNTIES = {
    'wake': 'monthly',      # High volume county
    'durham': 'quarterly',
    'orange': 'quarterly',
    'chatham': 'quarterly',
    'lee': 'quarterly',
    'harnett': 'quarterly'
}

# Failure tracking file
FAILURES_DIR = Path('data/scrape_failures')


def get_failures_file(year):
    """Get path to failures tracking file for a year."""
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    return FAILURES_DIR / f'failures_{year}.json'


def load_failures(year):
    """Load existing failures from file."""
    failures_file = get_failures_file(year)
    if failures_file.exists():
        with open(failures_file, 'r') as f:
            return json.load(f)
    return []


def save_failures(year, failures):
    """Save failures to file."""
    failures_file = get_failures_file(year)
    with open(failures_file, 'w') as f:
        json.dump(failures, f, indent=2, default=str)
    logger.info(f"Saved {len(failures)} failures to {failures_file}")


def get_date_ranges(year, strategy):
    """Generate date ranges based on strategy."""
    ranges = []

    if strategy == 'monthly':
        for month in range(1, 13):
            start = date(year, month, 1)
            if month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month + 1, 1) - relativedelta(days=1)
            ranges.append((start, end))

    elif strategy == 'quarterly':
        quarters = [
            (date(year, 1, 1), date(year, 3, 31)),
            (date(year, 4, 1), date(year, 6, 30)),
            (date(year, 7, 1), date(year, 9, 30)),
            (date(year, 10, 1), date(year, 12, 31))
        ]
        ranges = quarters

    elif strategy == 'bimonthly':
        bimonthly = [
            (date(year, 1, 1), date(year, 2, 29 if year % 4 == 0 else 28)),
            (date(year, 3, 1), date(year, 4, 30)),
            (date(year, 5, 1), date(year, 6, 30)),
            (date(year, 7, 1), date(year, 8, 31)),
            (date(year, 9, 1), date(year, 10, 31)),
            (date(year, 11, 1), date(year, 12, 31))
        ]
        ranges = bimonthly

    return ranges


def split_quarter_to_bimonthly(start_date, end_date):
    """Split a quarterly range into bi-monthly ranges."""
    mid_date = start_date + relativedelta(months=2) - relativedelta(days=1)
    second_start = mid_date + relativedelta(days=1)
    return [
        (start_date, mid_date),
        (second_start, end_date)
    ]


def run_single_scrape(county, start_date, end_date, dry_run=False):
    """Run a single scrape and return result dict."""
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    if dry_run:
        logger.info(f"[DRY RUN] {county.title()}: {start_str} to {end_str}")
        return {
            'success': True,
            'county': county,
            'start_date': start_str,
            'end_date': end_str,
            'cases_found': 0,
            'cases_processed': 0,
            'too_many_results': False,
            'error': None
        }

    try:
        scraper = InitialScraper(
            county=county,
            start_date=start_str,
            end_date=end_str,
            test_mode=False,
            limit=None
        )
        scraper.run()

        # Get results from scrape log
        from database.connection import get_session
        from database.models import ScrapeLog
        with get_session() as session:
            log = session.query(ScrapeLog).filter_by(id=scraper.scrape_log_id).first()
            if log:
                return {
                    'success': log.status == 'success',
                    'county': county,
                    'start_date': start_str,
                    'end_date': end_str,
                    'cases_found': log.cases_found or 0,
                    'cases_processed': log.cases_processed or 0,
                    'too_many_results': False,
                    'error': log.error_message
                }

        return {
            'success': True,
            'county': county,
            'start_date': start_str,
            'end_date': end_str,
            'cases_found': 0,
            'cases_processed': 0,
            'too_many_results': False,
            'error': None
        }

    except TruncatedResultsError as e:
        return {
            'success': False,
            'county': county,
            'start_date': start_str,
            'end_date': end_str,
            'cases_found': 0,
            'cases_processed': 0,
            'too_many_results': True,
            'error': str(e)
        }

    except Exception as e:
        error_msg = str(e).lower()
        return {
            'success': False,
            'county': county,
            'start_date': start_str,
            'end_date': end_str,
            'cases_found': 0,
            'cases_processed': 0,
            'too_many_results': 'too many' in error_msg or 'could have returned more' in error_msg,
            'error': str(e)
        }


def scrape_county_ranges(county, year, dry_run=False):
    """Scrape all date ranges for a single county.

    This function runs in its own thread with its own browser.
    """
    strategy = COUNTIES[county]
    date_ranges = get_date_ranges(year, strategy)

    results = {
        'county': county,
        'strategy': strategy,
        'total_ranges': len(date_ranges),
        'succeeded': 0,
        'cases_found': 0,
        'cases_processed': 0,
        'failures': []
    }

    logger.info(f"[{county.upper()}] Starting {strategy} scrape ({len(date_ranges)} ranges)")

    for start_date, end_date in date_ranges:
        result = run_single_scrape(county, start_date, end_date, dry_run)

        if result['success']:
            results['succeeded'] += 1
            results['cases_found'] += result['cases_found']
            results['cases_processed'] += result['cases_processed']
            logger.info(f"[{county.upper()}] ✓ {start_date} to {end_date}: {result['cases_processed']} foreclosures")

        elif result['too_many_results'] and strategy == 'quarterly':
            # Fall back to bi-monthly
            logger.warning(f"[{county.upper()}] Too many results, splitting to bi-monthly...")
            bimonthly_ranges = split_quarter_to_bimonthly(start_date, end_date)

            for bi_start, bi_end in bimonthly_ranges:
                bi_result = run_single_scrape(county, bi_start, bi_end, dry_run)
                if bi_result['success']:
                    results['succeeded'] += 1
                    results['cases_found'] += bi_result['cases_found']
                    results['cases_processed'] += bi_result['cases_processed']
                    logger.info(f"[{county.upper()}] ✓ {bi_start} to {bi_end}: {bi_result['cases_processed']} foreclosures")
                else:
                    results['failures'].append({
                        'county': county,
                        'start_date': str(bi_start),
                        'end_date': str(bi_end),
                        'error': bi_result['error'],
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.error(f"[{county.upper()}] ✗ {bi_start} to {bi_end}: {bi_result['error']}")
        else:
            results['failures'].append({
                'county': county,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'error': result['error'],
                'timestamp': datetime.now().isoformat()
            })
            logger.error(f"[{county.upper()}] ✗ {start_date} to {end_date}: {result['error']}")

    logger.info(f"[{county.upper()}] Complete: {results['succeeded']}/{results['total_ranges']} ranges, {results['cases_processed']} foreclosures")
    return results


def run_parallel_scrape(year, counties, dry_run=False, max_workers=6):
    """Run scrapes for multiple counties in parallel (year mode with monthly/quarterly splits)."""

    logger.info("="*60)
    logger.info("PARALLEL BATCH SCRAPE")
    logger.info("="*60)
    logger.info(f"Year: {year}")
    logger.info(f"Counties: {', '.join(counties)}")
    logger.info(f"Parallel workers: {max_workers}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("="*60)

    all_results = []
    all_failures = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all county scrapes
        future_to_county = {
            executor.submit(scrape_county_ranges, county, year, dry_run): county
            for county in counties
        }

        # Collect results as they complete
        for future in as_completed(future_to_county):
            county = future_to_county[future]
            try:
                result = future.result()
                all_results.append(result)
                all_failures.extend(result['failures'])
            except Exception as e:
                logger.error(f"[{county.upper()}] Thread failed: {e}")
                all_failures.append({
                    'county': county,
                    'start_date': f'{year}-01-01',
                    'end_date': f'{year}-12-31',
                    'error': f'Thread failed: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })

    return all_results, all_failures


def run_date_range_scrape(start_date, end_date, counties, dry_run=False, max_workers=6):
    """Run scrapes for multiple counties in parallel (date range mode - same range for all)."""

    logger.info("="*60)
    logger.info("PARALLEL DATE RANGE SCRAPE")
    logger.info("="*60)
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Counties: {', '.join(counties)}")
    logger.info(f"Parallel workers: {max_workers}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("="*60)

    all_results = []
    all_failures = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all county scrapes with the same date range
        future_to_county = {
            executor.submit(run_single_scrape, county, start_date, end_date, dry_run): county
            for county in counties
        }

        # Collect results as they complete
        for future in as_completed(future_to_county):
            county = future_to_county[future]
            try:
                result = future.result()
                # Convert single scrape result to county result format
                county_result = {
                    'county': county,
                    'strategy': 'date_range',
                    'total_ranges': 1,
                    'succeeded': 1 if result['success'] else 0,
                    'cases_found': result['cases_found'],
                    'cases_processed': result['cases_processed'],
                    'failures': []
                }
                if not result['success']:
                    county_result['failures'].append({
                        'county': county,
                        'start_date': str(start_date),
                        'end_date': str(end_date),
                        'error': result['error'],
                        'timestamp': datetime.now().isoformat()
                    })
                    all_failures.append(county_result['failures'][0])
                all_results.append(county_result)

                status = "✓" if result['success'] else "✗"
                logger.info(f"[{county.upper()}] {status} {result['cases_processed']} foreclosures")

            except Exception as e:
                logger.error(f"[{county.upper()}] Thread failed: {e}")
                all_failures.append({
                    'county': county,
                    'start_date': str(start_date),
                    'end_date': str(end_date),
                    'error': f'Thread failed: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })
                all_results.append({
                    'county': county,
                    'strategy': 'date_range',
                    'total_ranges': 1,
                    'succeeded': 0,
                    'cases_found': 0,
                    'cases_processed': 0,
                    'failures': [all_failures[-1]]
                })

    return all_results, all_failures


def print_summary(results, failures, identifier):
    """Print summary and save failures.

    Args:
        results: List of county result dicts
        failures: List of failure dicts
        identifier: Year (int) or date range string for failure tracking
    """

    logger.info("\n" + "="*60)
    logger.info("SCRAPE SUMMARY")
    logger.info("="*60)

    total_ranges = 0
    total_succeeded = 0
    total_found = 0
    total_processed = 0

    for result in results:
        county = result['county']
        logger.info(f"{county.title()} County ({result['strategy']}):")
        logger.info(f"  Ranges: {result['succeeded']}/{result['total_ranges']}")
        logger.info(f"  Cases found: {result['cases_found']}")
        logger.info(f"  Foreclosures saved: {result['cases_processed']}")

        if result['failures']:
            logger.warning(f"  Failures: {len(result['failures'])}")
        else:
            logger.info(f"  Status: ✓ COMPLETE")

        total_ranges += result['total_ranges']
        total_succeeded += result['succeeded']
        total_found += result['cases_found']
        total_processed += result['cases_processed']

    logger.info("-"*60)
    logger.info("TOTALS:")
    logger.info(f"  Ranges: {total_succeeded}/{total_ranges}")
    logger.info(f"  Cases found: {total_found}")
    logger.info(f"  Foreclosures saved: {total_processed}")

    if failures:
        logger.warning("-"*60)
        logger.warning(f"FAILURES ({len(failures)} total):")
        for f in failures:
            logger.warning(f"  {f['county'].title()}: {f['start_date']} to {f['end_date']}")
            logger.warning(f"    Error: {f['error'][:80]}...")

        # Save failures for retry (only for year mode)
        if isinstance(identifier, int):
            save_failures(identifier, failures)
            logger.info(f"\nTo retry failures: python scraper/parallel_batch_scrape.py --year {identifier} --retry-failures")
        else:
            logger.info(f"\nTo retry: python scraper/parallel_batch_scrape.py --start {failures[0]['start_date']} --end {failures[0]['end_date']}")
    else:
        logger.info("-"*60)
        logger.info("✓ 100% VALIDATION - ALL RANGES COMPLETE")
        # Clear any old failures file (only for year mode)
        if isinstance(identifier, int):
            failures_file = get_failures_file(identifier)
            if failures_file.exists():
                failures_file.unlink()

    logger.info("="*60)

    return len(failures) == 0


def retry_failures(year, dry_run=False):
    """Retry only the failed ranges from a previous run."""

    failures = load_failures(year)
    if not failures:
        logger.info(f"No failures to retry for {year}")
        return True

    logger.info("="*60)
    logger.info("RETRYING FAILED RANGES")
    logger.info("="*60)
    logger.info(f"Found {len(failures)} failures to retry")
    logger.info("="*60)

    new_failures = []
    succeeded = 0

    for failure in failures:
        county = failure['county']
        start_date = datetime.strptime(failure['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(failure['end_date'], '%Y-%m-%d').date()

        logger.info(f"Retrying {county.title()}: {start_date} to {end_date}")
        result = run_single_scrape(county, start_date, end_date, dry_run)

        if result['success']:
            succeeded += 1
            logger.info(f"  ✓ Success: {result['cases_processed']} foreclosures")
        else:
            new_failures.append({
                'county': county,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'error': result['error'],
                'timestamp': datetime.now().isoformat()
            })
            logger.error(f"  ✗ Still failing: {result['error'][:80]}...")

    logger.info("-"*60)
    logger.info(f"RETRY SUMMARY: {succeeded}/{len(failures)} succeeded")

    if new_failures:
        save_failures(year, new_failures)
        logger.warning(f"{len(new_failures)} ranges still failing")
        return False
    else:
        # Clear failures file
        failures_file = get_failures_file(year)
        if failures_file.exists():
            failures_file.unlink()
        logger.info("✓ ALL RETRIES SUCCEEDED - 100% VALIDATION")
        return True


def main():
    parser = argparse.ArgumentParser(description='Parallel batch scrape for NC foreclosures')

    # Mode selection: either --year OR --start/--end
    parser.add_argument('--year', type=int, help='Year to scrape (uses monthly/quarterly splits)')
    parser.add_argument('--start', type=str, help='Start date YYYY-MM-DD (for date range mode)')
    parser.add_argument('--end', type=str, help='End date YYYY-MM-DD (for date range mode)')

    # Common options
    parser.add_argument('--county', type=str, help='Specific county (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--retry-failures', action='store_true', help='Only retry failed ranges (year mode only)')
    parser.add_argument('--run-ocr', action='store_true', help='Run OCR after scrape')
    parser.add_argument('--workers', type=int, default=6, help='Number of parallel workers')

    args = parser.parse_args()

    # Validate mode: either --year or --start/--end, not both, not neither
    if args.year and (args.start or args.end):
        parser.error('Cannot use --year with --start/--end. Choose one mode.')
    if not args.year and not (args.start and args.end):
        parser.error('Either --year or both --start and --end are required.')
    if (args.start and not args.end) or (args.end and not args.start):
        parser.error('Both --start and --end must be provided together.')

    # Determine mode
    date_range_mode = args.start and args.end

    # Validate dates/year
    if date_range_mode:
        try:
            start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
            end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
        except ValueError:
            parser.error('Invalid date format. Use YYYY-MM-DD.')
        if start_date > end_date:
            parser.error('Start date must be before or equal to end date.')
        if args.retry_failures:
            parser.error('--retry-failures is only available in year mode.')
    else:
        current_year = datetime.now().year
        if args.year < 2020 or args.year > current_year:
            logger.error(f"Invalid year: {args.year}")
            sys.exit(1)

    # Verify VPN
    if not args.dry_run:
        verify_vpn_or_exit(
            auto_start=config.VPN_AUTO_START,
            sudo_password=config.SUDO_PASSWORD
        )

    # Determine counties
    if args.county:
        if args.county.lower() not in COUNTIES:
            logger.error(f"Invalid county: {args.county}")
            sys.exit(1)
        counties = [args.county.lower()]
    else:
        counties = list(COUNTIES.keys())

    # Run appropriate mode
    if date_range_mode:
        # Date range mode - single search for all counties (1 CAPTCHA)
        logger.info("Using single-search mode for date range (1 CAPTCHA for all counties)")
        result = run_single_search_scrape(
            start_date,
            end_date,
            counties,
            dry_run=args.dry_run
        )
        success = result['status'] in ('success', 'dry_run')
        if not success:
            logger.error(f"Date range scrape failed: {result.get('error')}")
    elif args.retry_failures:
        # Year mode - retry failures
        success = retry_failures(args.year, args.dry_run)
    else:
        # Year mode - full scrape with monthly/quarterly splits
        results, failures = run_parallel_scrape(
            args.year,
            counties,
            args.dry_run,
            max_workers=min(args.workers, len(counties))
        )
        success = print_summary(results, failures, args.year)

    # Run OCR if requested
    if args.run_ocr and not args.dry_run:
        logger.info("\n" + "="*60)
        logger.info("STARTING OCR PROCESSING")
        logger.info("="*60)

        from ocr.processor import process_unprocessed_documents
        try:
            ocr_count = process_unprocessed_documents()
            logger.info(f"OCR completed: {ocr_count} documents processed")
        except Exception as e:
            logger.error(f"OCR failed: {e}")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
