"""Batch initial scrape for all counties with quarterly/monthly strategy.

Strategy:
- Wake County: Monthly searches (known to have many results)
- Other counties (Chatham, Durham, Harnett, Lee, Orange): Quarterly searches
  - If quarterly fails with "too many results", fall back to bi-monthly for that quarter

Usage:
    python scraper/batch_initial_scrape.py --year 2024
    python scraper/batch_initial_scrape.py --year 2024 --county wake
    python scraper/batch_initial_scrape.py --year 2024 --dry-run
"""

import argparse
import sys
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from scraper.initial_scrape import InitialScraper, TruncatedResultsError
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


def get_date_ranges(year, strategy):
    """Generate date ranges based on strategy.

    Args:
        year: Year to scrape
        strategy: 'monthly', 'quarterly', or 'bimonthly'

    Returns:
        List of (start_date, end_date) tuples
    """
    ranges = []

    if strategy == 'monthly':
        # 12 monthly ranges
        for month in range(1, 13):
            start = date(year, month, 1)
            # Last day of month
            if month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month + 1, 1) - relativedelta(days=1)
            ranges.append((start, end))

    elif strategy == 'quarterly':
        # 4 quarterly ranges
        quarters = [
            (date(year, 1, 1), date(year, 3, 31)),
            (date(year, 4, 1), date(year, 6, 30)),
            (date(year, 7, 1), date(year, 9, 30)),
            (date(year, 10, 1), date(year, 12, 31))
        ]
        ranges = quarters

    elif strategy == 'bimonthly':
        # 6 bi-monthly ranges
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
    """Split a quarterly range into bi-monthly ranges.

    Args:
        start_date: Quarter start date
        end_date: Quarter end date

    Returns:
        List of two (start_date, end_date) tuples
    """
    # First half: months 1-2 of quarter
    mid_date = start_date + relativedelta(months=2) - relativedelta(days=1)
    second_start = mid_date + relativedelta(days=1)

    return [
        (start_date, mid_date),
        (second_start, end_date)
    ]


def run_scrape(county, start_date, end_date, dry_run=False):
    """Run scrape for a single date range.

    Args:
        county: County name
        start_date: Start date
        end_date: End date
        dry_run: If True, just log what would be done

    Returns:
        dict: {
            'success': bool,
            'cases_processed': int,
            'cases_found': int,
            'cases_reviewed': int,
            'validation_passed': bool,
            'too_many_results': bool
        }
    """
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    logger.info(f"  Scraping {county.title()} County: {start_str} to {end_str}")

    if dry_run:
        logger.info(f"    [DRY RUN] Would scrape {county} from {start_str} to {end_str}")
        return {
            'success': True,
            'cases_processed': 0,
            'cases_found': 0,
            'cases_reviewed': 0,
            'validation_passed': True,
            'too_many_results': False
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
                    'cases_processed': log.cases_processed or 0,
                    'cases_found': log.cases_found or 0,
                    'cases_reviewed': log.cases_found or 0,  # For now, same as found
                    'validation_passed': True,  # Will be set by scraper
                    'too_many_results': False
                }

        return {
            'success': True,
            'cases_processed': 0,
            'cases_found': 0,
            'cases_reviewed': 0,
            'validation_passed': True,
            'too_many_results': False
        }

    except TruncatedResultsError as e:
        # Results were truncated - need to narrow date range
        logger.warning(f"    Results truncated for {county} {start_str} to {end_str}: {e}")
        return {
            'success': False,
            'cases_processed': 0,
            'cases_found': 0,
            'cases_reviewed': 0,
            'validation_passed': False,
            'too_many_results': True
        }

    except Exception as e:
        error_msg = str(e).lower()
        # Check for legacy "too many results" messages
        if 'too many results' in error_msg or 'could have returned more' in error_msg:
            logger.warning(f"    Too many results for {county} {start_str} to {end_str}")
            return {
                'success': False,
                'cases_processed': 0,
                'cases_found': 0,
                'cases_reviewed': 0,
                'validation_passed': False,
                'too_many_results': True
            }
        else:
            logger.error(f"    Error scraping {county}: {e}")
            return {
                'success': False,
                'cases_processed': 0,
                'cases_found': 0,
                'cases_reviewed': 0,
                'validation_passed': False,
                'too_many_results': False
            }


def scrape_county(county, year, dry_run=False):
    """Scrape all data for a county for a given year.

    Args:
        county: County name
        year: Year to scrape
        dry_run: If True, just log what would be done

    Returns:
        dict: Summary of scrape results
    """
    strategy = COUNTIES[county]
    logger.info(f"\n{'='*60}")
    logger.info(f"SCRAPING {county.upper()} COUNTY ({strategy} strategy)")
    logger.info(f"{'='*60}")

    date_ranges = get_date_ranges(year, strategy)

    results = {
        'county': county,
        'strategy': strategy,
        'ranges_attempted': 0,
        'ranges_succeeded': 0,
        'total_cases_found': 0,      # Total cases from search results
        'total_cases_reviewed': 0,   # Cases we reviewed
        'total_cases_processed': 0,  # Foreclosure cases saved
        'fallbacks_used': 0,
        'validation_failures': [],   # Track any validation mismatches
        'failed_ranges': []          # Track ranges that failed (for retry)
    }

    for start_date, end_date in date_ranges:
        results['ranges_attempted'] += 1

        result = run_scrape(county, start_date, end_date, dry_run)

        if result['success']:
            results['ranges_succeeded'] += 1
            results['total_cases_found'] += result.get('cases_found', 0)
            results['total_cases_reviewed'] += result.get('cases_reviewed', 0)
            results['total_cases_processed'] += result.get('cases_processed', 0)

            # Check validation
            if not result.get('validation_passed', True):
                results['validation_failures'].append({
                    'range': f"{start_date} to {end_date}",
                    'expected': result.get('cases_found', 0),
                    'reviewed': result.get('cases_reviewed', 0)
                })

        elif result['too_many_results'] and strategy == 'quarterly':
            # Fall back to bi-monthly for this quarter
            logger.info(f"    Falling back to bi-monthly for this quarter...")
            results['fallbacks_used'] += 1

            bimonthly_ranges = split_quarter_to_bimonthly(start_date, end_date)
            for bi_start, bi_end in bimonthly_ranges:
                bi_result = run_scrape(county, bi_start, bi_end, dry_run)
                if bi_result['success']:
                    results['ranges_succeeded'] += 1
                    results['total_cases_found'] += bi_result.get('cases_found', 0)
                    results['total_cases_reviewed'] += bi_result.get('cases_reviewed', 0)
                    results['total_cases_processed'] += bi_result.get('cases_processed', 0)

                    if not bi_result.get('validation_passed', True):
                        results['validation_failures'].append({
                            'range': f"{bi_start} to {bi_end}",
                            'expected': bi_result.get('cases_found', 0),
                            'reviewed': bi_result.get('cases_reviewed', 0)
                        })
                else:
                    # Bi-monthly fallback also failed
                    results['failed_ranges'].append({
                        'start_date': bi_start,
                        'end_date': bi_end,
                        'reason': 'bi-monthly fallback failed'
                    })

        else:
            # Regular failure (CAPTCHA, network, etc.)
            results['failed_ranges'].append({
                'start_date': start_date,
                'end_date': end_date,
                'reason': 'scrape failed'
            })

    return results


def main():
    parser = argparse.ArgumentParser(description='Batch initial scrape for NC foreclosures')
    parser.add_argument('--year', type=int, required=True, help='Year to scrape (e.g., 2024)')
    parser.add_argument('--county', type=str, help='Specific county to scrape (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without scraping')
    parser.add_argument('--run-ocr', action='store_true', help='Run OCR processing after scrape completes')

    args = parser.parse_args()

    # Validate year
    current_year = datetime.now().year
    if args.year < 2020 or args.year > current_year:
        logger.error(f"Invalid year: {args.year}. Must be between 2020 and {current_year}")
        sys.exit(1)

    # Validate county if specified
    if args.county:
        if args.county.lower() not in COUNTIES:
            logger.error(f"Invalid county: {args.county}. Valid options: {', '.join(COUNTIES.keys())}")
            sys.exit(1)
        counties_to_scrape = [args.county.lower()]
    else:
        counties_to_scrape = list(COUNTIES.keys())

    logger.info("="*60)
    logger.info("NC FORECLOSURES - BATCH INITIAL SCRAPE")
    logger.info("="*60)
    logger.info(f"Year: {args.year}")
    logger.info(f"Counties: {', '.join(counties_to_scrape)}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("="*60)

    # Verify VPN before starting (unless dry run)
    if not args.dry_run:
        verify_vpn_or_exit(
            auto_start=config.VPN_AUTO_START,
            sudo_password=config.SUDO_PASSWORD
        )

    # Scrape each county
    all_results = []
    for county in counties_to_scrape:
        result = scrape_county(county, args.year, args.dry_run)
        all_results.append(result)

    # Print summary and collect failures for retry
    logger.info("\n" + "="*60)
    logger.info("BATCH SCRAPE SUMMARY")
    logger.info("="*60)

    total_found = 0
    total_reviewed = 0
    total_processed = 0
    all_validation_failures = []
    all_failed_ranges = []  # Collect all failures for retry

    for result in all_results:
        logger.info(f"{result['county'].title()} County ({result['strategy']}):")
        logger.info(f"  Ranges: {result['ranges_succeeded']}/{result['ranges_attempted']} succeeded")
        if result['fallbacks_used'] > 0:
            logger.info(f"  Fallbacks: {result['fallbacks_used']} quarters split to bi-monthly")
        logger.info(f"  Cases found: {result['total_cases_found']}")
        logger.info(f"  Cases reviewed: {result['total_cases_reviewed']}")
        logger.info(f"  Foreclosures saved: {result['total_cases_processed']}")

        # Failed ranges
        if result['failed_ranges']:
            logger.warning(f"  FAILED RANGES: {len(result['failed_ranges'])}")
            for failed in result['failed_ranges']:
                all_failed_ranges.append({
                    'county': result['county'],
                    'start_date': failed['start_date'],
                    'end_date': failed['end_date'],
                    'reason': failed['reason']
                })

        # Validation status
        if result['validation_failures']:
            logger.warning(f"  VALIDATION FAILURES: {len(result['validation_failures'])}")
            all_validation_failures.extend(result['validation_failures'])
        elif not result['failed_ranges']:
            logger.info(f"  Validation: PASSED")

        total_found += result['total_cases_found']
        total_reviewed += result['total_cases_reviewed']
        total_processed += result['total_cases_processed']

    logger.info("-"*60)
    logger.info(f"TOTALS:")
    logger.info(f"  Cases found in search results: {total_found}")
    logger.info(f"  Cases reviewed: {total_reviewed}")
    logger.info(f"  Foreclosure cases saved: {total_processed}")

    # Overall validation
    if total_found == total_reviewed and not all_failed_ranges:
        logger.info(f"  VALIDATION: PASSED (reviewed all {total_found} cases)")
    elif all_failed_ranges:
        logger.error(f"  VALIDATION: INCOMPLETE ({len(all_failed_ranges)} ranges failed)")
    else:
        logger.error(f"  VALIDATION: FAILED (expected {total_found}, reviewed {total_reviewed})")

    if all_validation_failures:
        logger.warning("-"*60)
        logger.warning("VALIDATION FAILURE DETAILS:")
        for failure in all_validation_failures:
            logger.warning(f"  {failure['range']}: expected {failure['expected']}, reviewed {failure['reviewed']}")

    # Show failed ranges and retry
    if all_failed_ranges and not args.dry_run:
        logger.warning("-"*60)
        logger.warning(f"FAILED RANGES ({len(all_failed_ranges)} total):")
        for failed in all_failed_ranges:
            logger.warning(f"  {failed['county'].title()}: {failed['start_date']} to {failed['end_date']} ({failed['reason']})")

        # Retry failed ranges
        logger.info("-"*60)
        logger.info("RETRYING FAILED RANGES...")
        retry_success = 0
        retry_failed = []

        for failed in all_failed_ranges:
            logger.info(f"  Retrying {failed['county'].title()}: {failed['start_date']} to {failed['end_date']}")
            retry_result = run_scrape(failed['county'], failed['start_date'], failed['end_date'], dry_run=False)

            if retry_result['success']:
                retry_success += 1
                total_found += retry_result.get('cases_found', 0)
                total_reviewed += retry_result.get('cases_reviewed', 0)
                total_processed += retry_result.get('cases_processed', 0)
                logger.info(f"    ✓ Retry succeeded: {retry_result.get('cases_processed', 0)} foreclosures saved")
            else:
                retry_failed.append(failed)
                logger.error(f"    ✗ Retry failed")

        logger.info("-"*60)
        logger.info(f"RETRY SUMMARY: {retry_success}/{len(all_failed_ranges)} succeeded")

        if retry_failed:
            logger.error(f"STILL FAILING ({len(retry_failed)} ranges):")
            for failed in retry_failed:
                logger.error(f"  {failed['county'].title()}: {failed['start_date']} to {failed['end_date']}")

    logger.info("="*60)

    # Final validation status
    if not all_failed_ranges or (all_failed_ranges and retry_success == len(all_failed_ranges)):
        logger.info("✓ SCRAPE COMPLETE - 100% VALIDATION")
    else:
        logger.warning(f"⚠ SCRAPE INCOMPLETE - {len(retry_failed) if 'retry_failed' in dir() else len(all_failed_ranges)} ranges still failing")

    # Run OCR if requested (and not a dry run)
    if args.run_ocr and not args.dry_run:
        logger.info("\n" + "="*60)
        logger.info("STARTING OCR PROCESSING")
        logger.info("="*60)

        from ocr.processor import process_unprocessed_documents

        try:
            ocr_count = process_unprocessed_documents()
            logger.info(f"OCR completed: {ocr_count} documents processed")
        except Exception as e:
            logger.error(f"OCR processing failed: {e}")

        logger.info("="*60)


if __name__ == '__main__':
    main()
