#!/usr/bin/env python3
"""
Backfill Wake RE enrichments for existing upset_bid cases.

This script enriches Wake County upset_bid cases with property URLs
from the Wake County Real Estate portal. It uses parcel IDs when available,
with address-based search as a fallback.

Usage:
    PYTHONPATH=$(pwd) venv/bin/python scripts/backfill_wake_enrichments.py [--dry-run] [--limit N]
"""

import argparse
import logging
import sys
import time

# Add project root to path
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

from sqlalchemy import or_
from database.connection import get_session
from database.models import Case
from enrichments.common.models import Enrichment
from enrichments.wake_re import enrich_case
from enrichments.wake_re.config import COUNTY_CODE
from common.logger import setup_logger


logger = setup_logger('backfill_wake_enrichments')


def get_cases_needing_enrichment():
    """
    Get Wake County upset_bid cases without enrichment.

    Excludes cases that already have wake_re_url or wake_re_error set.
    Orders by deadline (earliest first) to prioritize urgent cases.

    Returns:
        list: List of dicts with case data (id, case_number, parcel_id, property_address, next_bid_deadline)
    """
    with get_session() as session:
        # Subquery for cases with existing enrichment (success or error)
        enriched_case_ids = session.query(Enrichment.case_id).filter(
            Enrichment.case_id.isnot(None),
            or_(
                Enrichment.wake_re_url.isnot(None),
                Enrichment.wake_re_error.isnot(None)
            )
        ).scalar_subquery()

        # Get cases without enrichment
        cases = session.query(Case).filter(
            Case.county_code == COUNTY_CODE,
            Case.classification == 'upset_bid',
            Case.id.notin_(enriched_case_ids),
        ).order_by(Case.next_bid_deadline.asc()).all()

        # Convert to dicts to avoid detached instance errors
        case_data = []
        for case in cases:
            case_data.append({
                'id': case.id,
                'case_number': case.case_number,
                'parcel_id': case.parcel_id,
                'property_address': case.property_address,
                'next_bid_deadline': case.next_bid_deadline,
            })

        return case_data


def run_backfill(dry_run: bool = False, limit: int = None):
    """
    Run the backfill process.

    Args:
        dry_run: If True, show what would be done without making changes
        limit: Maximum number of cases to process (for testing)
    """
    cases = get_cases_needing_enrichment()

    if limit:
        cases = cases[:limit]

    logger.info(f"Found {len(cases)} Wake County upset_bid cases needing enrichment")

    if len(cases) == 0:
        logger.info("No cases need enrichment. Exiting.")
        return

    print("\n" + "=" * 70)
    print("Wake County RE Enrichment Backfill")
    print("=" * 70)
    print(f"Cases to enrich: {len(cases)}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will update database)'}")
    print("=" * 70 + "\n")

    if dry_run:
        print("DRY RUN - Cases that would be enriched:\n")
        for i, case in enumerate(cases, 1):
            parcel_info = f"parcel={case['parcel_id']}" if case['parcel_id'] else "no parcel"
            addr_info = f"addr={case['property_address'][:50]}..." if case['property_address'] else "no address"
            deadline = case['next_bid_deadline'].strftime('%Y-%m-%d') if case['next_bid_deadline'] else 'no deadline'

            print(f"[{i:3d}] {case['case_number']}")
            print(f"      Deadline: {deadline}")
            print(f"      {parcel_info}")
            print(f"      {addr_info}")
            print()

        print(f"\nDRY RUN complete. Would enrich {len(cases)} cases.")
        print("Run without --dry-run to execute.")
        return

    # Live run
    success_count = 0
    error_count = 0
    review_count = 0

    print("Starting enrichment (rate-limited to 1 request/second)...\n")

    for i, case in enumerate(cases, 1):
        logger.info(f"[{i}/{len(cases)}] Enriching {case['case_number']}...")

        deadline_str = case['next_bid_deadline'].strftime('%Y-%m-%d') if case['next_bid_deadline'] else 'N/A'
        print(f"[{i:3d}/{len(cases)}] {case['case_number']} (deadline: {deadline_str})")

        try:
            result = enrich_case(case['id'])

            if result.get('success'):
                success_count += 1
                url = result.get('url', 'N/A')
                account = result.get('account_id', 'N/A')
                print(f"      ✓ Success: Account {account}")
                print(f"        {url}")
                logger.info(f"  ✓ Success: {url}")
            elif result.get('review_needed'):
                review_count += 1
                error_msg = result.get('error', 'Unknown')
                print(f"      ! Needs review: {error_msg}")
                logger.warning(f"  ! Needs review: {error_msg}")
            else:
                error_count += 1
                error_msg = result.get('error', 'Unknown error')
                print(f"      ✗ Error: {error_msg}")
                logger.error(f"  ✗ Error: {error_msg}")

            # Rate limiting - be nice to Wake County servers
            if i < len(cases):  # Don't sleep after last case
                time.sleep(1)

        except Exception as e:
            error_count += 1
            print(f"      ✗ Exception: {e}")
            logger.exception(f"  ✗ Exception: {e}")

        # Progress update every 10 cases
        if i % 10 == 0 or i == len(cases):
            print(f"\n  Progress: {i}/{len(cases)} cases processed")
            print(f"  Success: {success_count} | Review: {review_count} | Error: {error_count}\n")

    # Final summary
    print("\n" + "=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"Total cases processed: {len(cases)}")
    print(f"  ✓ Success:          {success_count:4d} ({100*success_count/len(cases) if len(cases) > 0 else 0:.1f}%)")
    print(f"  ! Needs review:     {review_count:4d} ({100*review_count/len(cases) if len(cases) > 0 else 0:.1f}%)")
    print(f"  ✗ Errors:           {error_count:4d} ({100*error_count/len(cases) if len(cases) > 0 else 0:.1f}%)")
    print("=" * 70)

    if review_count > 0:
        print(f"\n{review_count} cases need manual review.")
        print("Check the enrichment_review_log table or use the Review Queue API.")

    logger.info(f"Backfill complete: {success_count} success, {review_count} review, {error_count} errors")


def main():
    """Parse arguments and run backfill."""
    parser = argparse.ArgumentParser(
        description='Backfill Wake RE enrichments for upset_bid cases',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be done
  %(prog)s --dry-run

  # Test with first 5 cases
  %(prog)s --limit 5

  # Run full backfill
  %(prog)s
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--limit',
        type=int,
        metavar='N',
        help='Limit to first N cases (for testing)'
    )
    args = parser.parse_args()

    # Run backfill (uses database.connection.get_session, no Flask context needed)
    run_backfill(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
