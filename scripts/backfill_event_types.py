#!/usr/bin/env python3
"""
Backfill NULL event types by re-parsing case pages.

This script fixes the parsing issue where event types split across
HTML elements were not captured (e.g., "Order" + "for Sale of Ward's Property").
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from database.connection import get_session
from database.models import Case, CaseEvent
from scraper.page_parser import parse_case_detail
from playwright.sync_api import sync_playwright
from common.logger import setup_logger

logger = setup_logger(__name__)


def get_cases_with_null_events():
    """Get all cases that have events with NULL event_type."""
    with get_session() as session:
        result = session.execute(text("""
            SELECT DISTINCT c.id, c.case_number, c.case_url, c.classification
            FROM cases c
            JOIN case_events e ON e.case_id = c.id
            WHERE e.event_type IS NULL AND e.event_date IS NOT NULL
            ORDER BY c.id
        """))
        return [dict(row._mapping) for row in result]


def process_case(case_info: dict) -> dict:
    """Re-parse a case and update NULL event types."""
    case_id = case_info['id']
    case_url = case_info['case_url']

    if not case_url:
        return {'case_id': case_id, 'status': 'skip', 'reason': 'no URL'}

    try:
        with sync_playwright() as p:
            # headless=False required for Angular pages to render properly
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            page.goto(case_url, wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(2000)  # Let Angular render

            html = page.content()
            case_data = parse_case_detail(html)

            browser.close()

        # Build lookup of parsed events by date
        parsed_events = {}
        for e in case_data.get('events', []):
            if e.get('event_date') and e.get('event_type'):
                try:
                    date_obj = datetime.strptime(e['event_date'], '%m/%d/%Y').date()
                    key = f"{date_obj}_{e['event_type'][:20]}"
                    parsed_events[str(date_obj)] = e
                except:
                    pass

        # Update NULL event types
        updated = 0
        with get_session() as session:
            null_events = session.query(CaseEvent).filter(
                CaseEvent.case_id == case_id,
                CaseEvent.event_type.is_(None),
                CaseEvent.event_date.isnot(None)
            ).all()

            for db_event in null_events:
                date_str = str(db_event.event_date)
                if date_str in parsed_events:
                    new_type = parsed_events[date_str].get('event_type')
                    if new_type:
                        db_event.event_type = new_type
                        updated += 1
                        logger.debug(f"  Updated {date_str}: {new_type}")

            session.commit()

        return {'case_id': case_id, 'status': 'success', 'updated': updated}

    except Exception as e:
        logger.error(f"Error processing case {case_id}: {e}")
        return {'case_id': case_id, 'status': 'error', 'error': str(e)}


def run_backfill(max_workers: int = 4, limit: int = None):
    """Run the backfill with parallel workers."""
    cases = get_cases_with_null_events()

    if limit:
        cases = cases[:limit]

    logger.info(f"Backfilling {len(cases)} cases with {max_workers} workers")

    stats = {'success': 0, 'error': 0, 'skip': 0, 'updated': 0}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_case, c): c for c in cases}

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            stats[result['status']] = stats.get(result['status'], 0) + 1
            if result.get('updated'):
                stats['updated'] += result['updated']

            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i+1}/{len(cases)} cases processed")

    logger.info(f"\n{'='*50}")
    logger.info(f"BACKFILL COMPLETE")
    logger.info(f"{'='*50}")
    logger.info(f"  Cases processed: {len(cases)}")
    logger.info(f"  Successful: {stats['success']}")
    logger.info(f"  Errors: {stats['error']}")
    logger.info(f"  Skipped: {stats['skip']}")
    logger.info(f"  Events updated: {stats['updated']}")

    return stats


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backfill NULL event types')
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--limit', type=int, help='Limit number of cases to process')
    args = parser.parse_args()

    run_backfill(max_workers=args.workers, limit=args.limit)
