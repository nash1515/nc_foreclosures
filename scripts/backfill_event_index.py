#!/usr/bin/env python3
"""
Backfill event_index for existing case_events by re-scraping cases.

This script:
1. Gets all cases that have events without event_index
2. Re-scrapes each case to get current event data with Index #
3. Matches existing events by signature and updates their event_index

Usage:
    python scripts/backfill_event_index.py
    python scripts/backfill_event_index.py --dry-run
    python scripts/backfill_event_index.py --limit 10
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from playwright.sync_api import sync_playwright
from database.connection import get_session
from database.models import Case, CaseEvent
from scraper.page_parser import parse_case_detail
from common.logger import setup_logger

logger = setup_logger(__name__)


def fetch_case_page(page, case_url: str, max_retries: int = 3) -> str:
    """Fetch case detail page with retry logic."""
    for attempt in range(max_retries):
        try:
            page.goto(case_url, wait_until='networkidle', timeout=30000)
            page.wait_for_selector('table.roa-caseinfo-info-rows', timeout=15000)
            return page.content()
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
            else:
                raise


def backfill_case_events(case: Case, page, dry_run: bool = False) -> int:
    """
    Backfill event_index for a case by re-scraping.

    Returns:
        Number of events updated
    """
    logger.info(f"Processing {case.case_number}...")

    try:
        html = fetch_case_page(page, case.case_url)
        case_data = parse_case_detail(html)
        parsed_events = case_data.get('events', [])

        if not parsed_events:
            logger.warning(f"  No events parsed from page")
            return 0

        # Create lookup by signature
        parsed_by_sig = {}
        for event in parsed_events:
            if event.get('event_index'):
                sig = (event.get('event_date'), (event.get('event_type') or '').strip().lower())
                parsed_by_sig[sig] = event['event_index']

        if not parsed_by_sig:
            logger.warning(f"  No events with Index # found on page")
            return 0

        # Update existing events
        updated = 0
        with get_session() as session:
            db_events = session.query(CaseEvent).filter(
                CaseEvent.case_id == case.id,
                CaseEvent.event_index.is_(None)
            ).all()

            for db_event in db_events:
                # Format date to match parser output
                event_date_str = db_event.event_date.strftime('%m/%d/%Y') if db_event.event_date else None
                sig = (event_date_str, (db_event.event_type or '').strip().lower())

                if sig in parsed_by_sig:
                    new_index = parsed_by_sig[sig]
                    if not dry_run:
                        db_event.event_index = new_index
                    logger.debug(f"  {db_event.event_type} ({event_date_str}) -> Index #{new_index}")
                    updated += 1

            if not dry_run:
                session.commit()

        logger.info(f"  Updated {updated} events with Index #")
        return updated

    except Exception as e:
        logger.error(f"  Error processing {case.case_number}: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Backfill event_index for existing events')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated')
    parser.add_argument('--limit', type=int, help='Limit number of cases to process')
    parser.add_argument('--classification', type=str, help='Only process cases with this classification')

    args = parser.parse_args()

    # Find cases with events missing event_index
    # Store case data as tuples to avoid session issues
    case_data = []
    with get_session() as session:
        query = session.query(Case).join(CaseEvent).filter(
            CaseEvent.event_index.is_(None)
        ).distinct()

        if args.classification:
            query = query.filter(Case.classification == args.classification)

        cases = query.all()

        if args.limit:
            cases = cases[:args.limit]

        # Extract needed data before session closes
        for case in cases:
            case_data.append({
                'id': case.id,
                'case_number': case.case_number,
                'case_url': case.case_url
            })

        logger.info(f"Found {len(case_data)} cases with events missing event_index")

    if not case_data:
        logger.info("No cases need backfill")
        return

    total_updated = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False for Angular
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()

        try:
            for i, case_dict in enumerate(case_data):
                logger.info(f"[{i+1}/{len(case_data)}] Processing {case_dict['case_number']}")
                # Create a simple object to pass to backfill_case_events
                class CaseProxy:
                    def __init__(self, data):
                        self.id = data['id']
                        self.case_number = data['case_number']
                        self.case_url = data['case_url']

                case_obj = CaseProxy(case_dict)
                updated = backfill_case_events(case_obj, page, dry_run=args.dry_run)
                total_updated += updated

                # Small delay to be nice to the server
                time.sleep(1)

        finally:
            browser.close()

    action = "Would update" if args.dry_run else "Updated"
    logger.info(f"Backfill complete: {action} {total_updated} events across {len(case_data)} cases")


if __name__ == '__main__':
    main()
