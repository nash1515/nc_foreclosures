"""Batch scrape with configurable date chunking.

Sequential batch scraper that uses DateRangeScraper to process date ranges in chunks.
Unlike batch_initial_scrape.py (which uses InitialScraper for year-based initial scraping),
this script is designed for flexible date range processing with configurable chunk sizes.

Usage:
    # Monthly chunks, all counties
    PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
        --start 2024-01-01 --end 2024-12-31 --chunk monthly

    # Quarterly chunks, single county
    PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
        --start 2024-01-01 --end 2024-12-31 --chunk quarterly --county wake

    # Weekly chunks with limit for testing
    PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
        --start 2024-01-01 --end 2024-01-31 --chunk weekly --limit 10

    # Dry run to see chunks
    PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
        --start 2024-01-01 --end 2024-12-31 --chunk monthly --dry-run
"""

import argparse
import sys
from datetime import datetime

from scraper.date_range_scrape import DateRangeScraper
from common.date_utils import generate_date_chunks, parse_date
from common.logger import setup_logger

logger = setup_logger(__name__)

# Target counties (when no --county specified)
TARGET_COUNTIES = ['wake', 'durham', 'orange', 'chatham', 'lee', 'harnett']


def run_batch_scrape(start_date, end_date, chunk_size, county=None, limit=None, dry_run=False):
    """
    Run batch scrape with configurable date chunking.

    Args:
        start_date: Start date (date object)
        end_date: End date (date object)
        chunk_size: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        county: Single county name (optional, default: all 6 counties)
        limit: Limit cases per chunk for testing (optional)
        dry_run: If True, show chunks without running

    Returns:
        dict: Summary of batch scrape results
    """
    # Generate chunks
    chunks = generate_date_chunks(start_date, end_date, chunk_size)
    total_chunks = len(chunks)

    logger.info("=" * 60)
    logger.info("BATCH SCRAPE WITH DATE CHUNKING")
    logger.info("=" * 60)
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Chunk size: {chunk_size}")
    logger.info(f"Total chunks: {total_chunks}")
    logger.info(f"Counties: {county or 'all 6 counties'}")
    if limit:
        logger.info(f"Limit: {limit} cases per chunk")
    if dry_run:
        logger.info("DRY RUN MODE - No actual scraping")
    logger.info("=" * 60)

    # Prepare counties list
    counties = [county] if county else None

    # Dry run: just show chunks
    if dry_run:
        logger.info("\nChunks to process:")
        for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
            logger.info(f"  Chunk {i}/{total_chunks}: {chunk_start} to {chunk_end}")
        logger.info("=" * 60)
        return {
            'total_chunks': total_chunks,
            'chunks_processed': 0,
            'total_cases': 0,
            'status': 'dry_run'
        }

    # Run scrape for each chunk
    results = {
        'total_chunks': total_chunks,
        'chunks_processed': 0,
        'chunks_succeeded': 0,
        'chunks_failed': 0,
        'total_cases': 0,
        'failed_chunks': []
    }

    for i, (chunk_start, chunk_end) in enumerate(chunks, 1):
        logger.info(f"\nProcessing chunk {i} of {total_chunks}: {chunk_start} to {chunk_end}")
        logger.info("-" * 60)

        try:
            scraper = DateRangeScraper(
                start_date=chunk_start.strftime('%Y-%m-%d'),
                end_date=chunk_end.strftime('%Y-%m-%d'),
                counties=counties,
                limit=limit
            )
            result = scraper.run()

            results['chunks_processed'] += 1

            if result['status'] == 'success':
                results['chunks_succeeded'] += 1
                cases_processed = result.get('cases_processed', 0)
                results['total_cases'] += cases_processed
                logger.info(f"✓ Chunk {i} completed: {cases_processed} foreclosures saved")
            else:
                results['chunks_failed'] += 1
                results['failed_chunks'].append({
                    'chunk_num': i,
                    'start_date': chunk_start,
                    'end_date': chunk_end,
                    'error': result.get('error', 'Unknown error')
                })
                logger.error(f"✗ Chunk {i} failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            results['chunks_processed'] += 1
            results['chunks_failed'] += 1
            results['failed_chunks'].append({
                'chunk_num': i,
                'start_date': chunk_start,
                'end_date': chunk_end,
                'error': str(e)
            })
            logger.error(f"✗ Chunk {i} failed with exception: {e}")
            # Continue to next chunk even on error

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("BATCH SCRAPE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total chunks: {results['total_chunks']}")
    logger.info(f"Chunks processed: {results['chunks_processed']}")
    logger.info(f"Chunks succeeded: {results['chunks_succeeded']}")
    logger.info(f"Chunks failed: {results['chunks_failed']}")
    logger.info(f"Total foreclosures saved: {results['total_cases']}")

    if results['failed_chunks']:
        logger.warning("\nFailed chunks:")
        for failed in results['failed_chunks']:
            logger.warning(f"  Chunk {failed['chunk_num']}: {failed['start_date']} to {failed['end_date']}")
            logger.warning(f"    Error: {failed['error']}")

    logger.info("=" * 60)

    # Set overall status
    if results['chunks_failed'] == 0:
        results['status'] = 'success'
        logger.info("✓ BATCH SCRAPE COMPLETE - ALL CHUNKS SUCCEEDED")
    elif results['chunks_succeeded'] == 0:
        results['status'] = 'failed'
        logger.error("✗ BATCH SCRAPE FAILED - NO CHUNKS SUCCEEDED")
    else:
        results['status'] = 'partial'
        logger.warning("⚠ BATCH SCRAPE PARTIAL - SOME CHUNKS FAILED")

    return results


def main():
    parser = argparse.ArgumentParser(description='Batch scrape with configurable date chunking')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument(
        '--chunk',
        required=True,
        choices=['daily', 'weekly', 'monthly', 'quarterly', 'yearly'],
        help='Chunk size for date ranges'
    )
    parser.add_argument('--county', help='Single county override (default: all 6 counties)')
    parser.add_argument('--limit', type=int, help='Limit cases per chunk for testing')
    parser.add_argument('--dry-run', action='store_true', help='Show chunks without running')

    args = parser.parse_args()

    # Parse and validate dates
    try:
        start_date = parse_date(args.start)
        end_date = parse_date(args.end)
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        logger.error("Date format must be YYYY-MM-DD")
        sys.exit(1)

    if start_date > end_date:
        logger.error(f"Start date ({start_date}) must be before end date ({end_date})")
        sys.exit(1)

    # Validate county if specified
    if args.county:
        if args.county.lower() not in TARGET_COUNTIES:
            logger.error(f"Invalid county: {args.county}")
            logger.error(f"Valid counties: {', '.join(TARGET_COUNTIES)}")
            sys.exit(1)
        county = args.county.lower()
    else:
        county = None

    # Run batch scrape
    results = run_batch_scrape(
        start_date=start_date,
        end_date=end_date,
        chunk_size=args.chunk,
        county=county,
        limit=args.limit,
        dry_run=args.dry_run
    )

    # Exit with appropriate code
    if results['status'] == 'success' or results['status'] == 'dry_run':
        sys.exit(0)
    elif results['status'] == 'partial':
        sys.exit(2)  # Partial success
    else:
        sys.exit(1)  # Complete failure


if __name__ == '__main__':
    main()
