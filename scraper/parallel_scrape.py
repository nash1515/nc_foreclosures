"""Parallel batch scrape with configurable date chunking.

Uses ThreadPoolExecutor to run multiple DateRangeScraper instances in parallel.
Each worker processes a different DATE CHUNK (not county) with its own browser instance.

This is safe because:
- Each DateRangeScraper creates its own isolated browser
- Date chunks are independent (no shared state)
- Workers process different time periods in parallel

Usage:
    # Monthly chunks, 3 workers (default)
    PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
        --start 2024-01-01 --end 2024-12-31 --chunk monthly

    # Quarterly chunks, 4 workers
    PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
        --start 2024-01-01 --end 2024-12-31 --chunk quarterly --workers 4

    # Weekly chunks with limit for testing
    PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
        --start 2024-01-01 --end 2024-01-31 --chunk weekly --limit 10 --workers 2

    # Dry run to see chunks
    PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
        --start 2024-01-01 --end 2024-12-31 --chunk monthly --dry-run

    # Single county with parallel processing
    PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
        --start 2024-01-01 --end 2024-06-30 --chunk monthly --county wake --workers 3
"""

import argparse
import sys
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from scraper.date_range_scrape import DateRangeScraper
from common.date_utils import generate_date_chunks, parse_date
from common.logger import setup_logger

logger = setup_logger(__name__)

# Target counties (when no --county specified)
TARGET_COUNTIES = ['wake', 'durham', 'orange', 'chatham', 'lee', 'harnett']

# Thread-safe lock for logging
log_lock = threading.Lock()


def run_chunk_scrape(chunk_num, total_chunks, chunk_start, chunk_end, county, limit, dry_run):
    """
    Run scrape for a single date chunk.

    This function runs in its own thread with its own browser.

    Args:
        chunk_num: Chunk number (for logging)
        total_chunks: Total number of chunks (for logging)
        chunk_start: Start date for this chunk
        chunk_end: End date for this chunk
        county: Single county name or None for all counties
        limit: Limit cases per chunk for testing
        dry_run: If True, just show what would be done

    Returns:
        dict: Result with chunk_num, success, cases, error, county
    """
    county_str = county if county else "all counties"
    chunk_id = f"Chunk {chunk_num}/{total_chunks}"

    with log_lock:
        logger.info(f"[{chunk_id}] Starting: {chunk_start} to {chunk_end} ({county_str})")

    if dry_run:
        with log_lock:
            logger.info(f"[{chunk_id}] [DRY RUN] Would process {county_str}")
        return {
            'chunk_num': chunk_num,
            'start_date': chunk_start,
            'end_date': chunk_end,
            'county': county,
            'success': True,
            'cases': 0,
            'error': None
        }

    try:
        # Prepare counties list for DateRangeScraper
        counties = [county] if county else None

        # Create scraper with its own browser
        scraper = DateRangeScraper(
            start_date=chunk_start.strftime('%Y-%m-%d'),
            end_date=chunk_end.strftime('%Y-%m-%d'),
            counties=counties,
            limit=limit
        )

        # Run scrape
        result = scraper.run()

        success = result['status'] == 'success'
        cases_processed = result.get('cases_processed', 0)
        error_message = result.get('error')

        with log_lock:
            if success:
                logger.info(f"[{chunk_id}] ✓ Completed: {cases_processed} foreclosures saved")
            else:
                logger.error(f"[{chunk_id}] ✗ Failed: {error_message}")

        return {
            'chunk_num': chunk_num,
            'start_date': chunk_start,
            'end_date': chunk_end,
            'county': county,
            'success': success,
            'cases': cases_processed,
            'error': error_message
        }

    except Exception as e:
        with log_lock:
            logger.error(f"[{chunk_id}] ✗ Exception: {e}")

        return {
            'chunk_num': chunk_num,
            'start_date': chunk_start,
            'end_date': chunk_end,
            'county': county,
            'success': False,
            'cases': 0,
            'error': str(e)
        }


def run_parallel_scrape(start_date, end_date, chunk_size, county=None, limit=None, dry_run=False, workers=3, per_county=False):
    """
    Run parallel batch scrape with configurable date chunking.

    Args:
        start_date: Start date (date object)
        end_date: End date (date object)
        chunk_size: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        county: Single county name (optional, default: all 6 counties)
        limit: Limit cases per chunk for testing (optional)
        dry_run: If True, show chunks without running
        workers: Number of parallel workers
        per_county: If True, search each county separately (recommended for backfills)

    Returns:
        dict: Summary of parallel scrape results
    """
    # Generate base date chunks
    date_chunks = generate_date_chunks(start_date, end_date, chunk_size)

    # Expand chunks to include county if per_county mode
    if per_county:
        chunks = []
        for chunk_start, chunk_end in date_chunks:
            for cnty in TARGET_COUNTIES:
                chunks.append((chunk_start, chunk_end, cnty))
        logger.info(f"Per-county mode: {len(date_chunks)} date chunks × {len(TARGET_COUNTIES)} counties = {len(chunks)} total searches")
    else:
        # Original behavior: just date chunks, all counties at once
        chunks = [(chunk_start, chunk_end, county) for chunk_start, chunk_end in date_chunks]

    total_chunks = len(chunks)

    logger.info("=" * 60)
    logger.info("PARALLEL BATCH SCRAPE WITH DATE CHUNKING")
    logger.info("=" * 60)
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Chunk size: {chunk_size}")
    logger.info(f"Total chunks: {total_chunks}")
    logger.info(f"Parallel workers: {workers}")
    if per_county:
        logger.info(f"Mode: Per-county (each county searched separately)")
    else:
        logger.info(f"Counties: {county or 'all 6 counties'}")
    if limit:
        logger.info(f"Limit: {limit} cases per chunk")
    if dry_run:
        logger.info("DRY RUN MODE - No actual scraping")
    logger.info("=" * 60)

    # Dry run: just show chunks
    if dry_run:
        logger.info("\nChunks to process in parallel:")
        for i, (chunk_start, chunk_end, cnty) in enumerate(chunks, 1):
            county_str = cnty if cnty else "all counties"
            logger.info(f"  Chunk {i}/{total_chunks}: {chunk_start} to {chunk_end} ({county_str})")
        logger.info("=" * 60)
        return {
            'total_chunks': total_chunks,
            'chunks_processed': 0,
            'chunks_succeeded': 0,
            'chunks_failed': 0,
            'total_cases': 0,
            'failed_chunks': [],
            'status': 'dry_run'
        }

    # Run scrapes in parallel
    results = {
        'total_chunks': total_chunks,
        'chunks_processed': 0,
        'chunks_succeeded': 0,
        'chunks_failed': 0,
        'total_cases': 0,
        'failed_chunks': []
    }

    # Use ThreadPoolExecutor to run chunks in parallel
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all chunks
        future_to_chunk = {
            executor.submit(
                run_chunk_scrape,
                i,
                total_chunks,
                chunk_start,
                chunk_end,
                cnty,
                limit,
                dry_run
            ): i
            for i, (chunk_start, chunk_end, cnty) in enumerate(chunks, 1)
        }

        # Collect results as they complete
        for future in as_completed(future_to_chunk):
            chunk_num = future_to_chunk[future]
            try:
                result = future.result()
                results['chunks_processed'] += 1

                if result['success']:
                    results['chunks_succeeded'] += 1
                    results['total_cases'] += result['cases']
                else:
                    results['chunks_failed'] += 1
                    results['failed_chunks'].append({
                        'chunk_num': result['chunk_num'],
                        'start_date': result['start_date'],
                        'end_date': result['end_date'],
                        'county': result.get('county'),
                        'error': result['error']
                    })

                # Progress update
                with log_lock:
                    logger.info(f"Overall progress: {results['chunks_processed']}/{total_chunks} chunks completed")

            except Exception as e:
                with log_lock:
                    logger.error(f"Thread for chunk {chunk_num} failed: {e}")
                results['chunks_processed'] += 1
                results['chunks_failed'] += 1
                results['failed_chunks'].append({
                    'chunk_num': chunk_num,
                    'start_date': None,
                    'end_date': None,
                    'error': f'Thread failed: {str(e)}'
                })

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("PARALLEL SCRAPE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total chunks: {results['total_chunks']}")
    logger.info(f"Chunks processed: {results['chunks_processed']}")
    logger.info(f"Chunks succeeded: {results['chunks_succeeded']}")
    logger.info(f"Chunks failed: {results['chunks_failed']}")
    logger.info(f"Total foreclosures saved: {results['total_cases']}")

    if results['failed_chunks']:
        logger.warning("\nFailed chunks:")
        for failed in results['failed_chunks']:
            county_info = f" ({failed['county']})" if failed.get('county') else ""
            logger.warning(f"  Chunk {failed['chunk_num']}: {failed['start_date']} to {failed['end_date']}{county_info}")
            logger.warning(f"    Error: {failed['error']}")

    logger.info("=" * 60)

    # Set overall status
    if results['chunks_failed'] == 0:
        results['status'] = 'success'
        logger.info("✓ PARALLEL SCRAPE COMPLETE - ALL CHUNKS SUCCEEDED")
    elif results['chunks_succeeded'] == 0:
        results['status'] = 'failed'
        logger.error("✗ PARALLEL SCRAPE FAILED - NO CHUNKS SUCCEEDED")
    else:
        results['status'] = 'partial'
        logger.warning("⚠ PARALLEL SCRAPE PARTIAL - SOME CHUNKS FAILED")

    return results


def main():
    parser = argparse.ArgumentParser(description='Parallel batch scrape with configurable date chunking')
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
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    parser.add_argument('--per-county', action='store_true',
                        help='Search each county separately to avoid result limits (recommended for backfills)')

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

    # Validate workers
    if args.workers < 1:
        logger.error("Workers must be at least 1")
        sys.exit(1)
    if args.workers > 10:
        logger.warning("Warning: More than 10 workers may cause issues. Limiting to 10.")
        args.workers = 10

    # Run parallel scrape
    results = run_parallel_scrape(
        start_date=start_date,
        end_date=end_date,
        chunk_size=args.chunk,
        county=county,
        limit=args.limit,
        dry_run=args.dry_run,
        workers=args.workers,
        per_county=args.per_county
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
