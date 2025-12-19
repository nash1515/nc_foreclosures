#!/usr/bin/env python3
"""
Re-evaluate dismissed skipped cases by fetching fresh events from the portal.

This addresses the gap where cases dismissed early may have later gained
sale events (like Report of Sale, Order for Sale, etc.) that make them
relevant upset bid opportunities.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from database.connection import get_session
from database.models import Case, CaseEvent, SkippedCase
from scraper.page_parser import parse_case_detail, is_foreclosure_case
from common.business_days import calculate_upset_bid_deadline
from playwright.sync_api import sync_playwright
from common.logger import setup_logger

logger = setup_logger(__name__)


def get_dismissed_cases(limit=None):
    """Get all dismissed skipped cases."""
    with get_session() as session:
        query = session.query(SkippedCase).filter(
            SkippedCase.review_action == 'dismissed'
        ).order_by(SkippedCase.file_date.desc())

        if limit:
            query = query.limit(limit)

        return [{'id': c.id, 'case_number': c.case_number, 'case_url': c.case_url,
                 'county_code': c.county_code, 'county_name': c.county_name,
                 'file_date': c.file_date}
                for c in query.all()]


def process_case(case_info: dict) -> dict:
    """Re-fetch a dismissed case and check if it now has sale indicators."""
    case_id = case_info['id']
    case_number = case_info['case_number']
    case_url = case_info['case_url']

    if not case_url:
        return {'case_id': case_id, 'case_number': case_number, 'status': 'skip', 'reason': 'no URL'}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            page.goto(case_url, wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(2000)

            html = page.content()
            case_data = parse_case_detail(html)

            browser.close()

        # Check if case now matches foreclosure/sale indicators
        if is_foreclosure_case(case_data):
            # Find sale event for deadline calculation
            sale_date = None
            for event in case_data.get('events', []):
                event_type = (event.get('event_type') or '').lower()
                if 'report of sale' in event_type:
                    if event.get('event_date'):
                        try:
                            sale_date = datetime.strptime(event['event_date'], '%m/%d/%Y').date()
                        except:
                            pass
                    break

            return {
                'case_id': case_id,
                'case_number': case_number,
                'status': 'promote',
                'case_data': case_data,
                'sale_date': sale_date,
                'case_info': case_info
            }
        else:
            return {'case_id': case_id, 'case_number': case_number, 'status': 'still_skip'}

    except Exception as e:
        logger.error(f"Error processing case {case_number}: {e}")
        return {'case_id': case_id, 'case_number': case_number, 'status': 'error', 'error': str(e)}


def promote_case_to_main(result: dict) -> bool:
    """Move a case from skipped_cases to main cases table."""
    case_info = result['case_info']
    case_data = result['case_data']
    sale_date = result.get('sale_date')

    try:
        with get_session() as session:
            # Check if already in main cases table
            existing = session.query(Case).filter_by(case_number=case_info['case_number']).first()
            if existing:
                logger.info(f"  Case {case_info['case_number']} already in main table")
                return False

            # Create new case
            new_case = Case(
                case_number=case_info['case_number'],
                county_code=case_info['county_code'],
                county_name=case_info['county_name'],
                case_type=case_data.get('case_type'),
                case_status=case_data.get('case_status'),
                file_date=case_info['file_date'],
                case_url=case_info['case_url'],
                style=case_data.get('style'),
                sale_date=sale_date
            )

            # Calculate deadline if we have sale date
            if sale_date:
                deadline = calculate_upset_bid_deadline(sale_date)
                new_case.next_bid_deadline = deadline
                # Check if still active
                if deadline >= date.today():
                    new_case.classification = 'upset_bid'
                else:
                    new_case.classification = 'closed_sold'
            else:
                new_case.classification = 'upcoming'

            # Extract address from events
            for event in case_data.get('events', []):
                if event.get('event_type') and 'report of sale' in event.get('event_type', '').lower():
                    if event.get('event_description'):
                        new_case.property_address = event['event_description'].strip()
                        break

            session.add(new_case)
            session.flush()  # Get the ID

            # Add events
            for event_data in case_data.get('events', []):
                event_date = None
                if event_data.get('event_date'):
                    try:
                        event_date = datetime.strptime(event_data['event_date'], '%m/%d/%Y').date()
                    except:
                        pass

                new_event = CaseEvent(
                    case_id=new_case.id,
                    event_date=event_date,
                    event_type=event_data.get('event_type'),
                    event_description=event_data.get('event_description'),
                    filed_by=event_data.get('filed_by'),
                    filed_against=event_data.get('filed_against')
                )
                session.add(new_event)

            # Mark skipped case as promoted
            skipped = session.query(SkippedCase).filter_by(id=case_info['id']).first()
            if skipped:
                skipped.review_action = 'promoted'

            session.commit()
            logger.info(f"  Promoted {case_info['case_number']} -> {new_case.classification}")
            return True

    except Exception as e:
        logger.error(f"Error promoting case {case_info['case_number']}: {e}")
        return False


def run_reevaluation(max_workers: int = 4, limit: int = None, dry_run: bool = False):
    """Re-evaluate dismissed cases."""
    cases = get_dismissed_cases(limit)

    logger.info(f"Re-evaluating {len(cases)} dismissed cases with {max_workers} workers")
    if dry_run:
        logger.info("DRY RUN - no changes will be made")

    stats = {'checked': 0, 'promote': 0, 'still_skip': 0, 'error': 0, 'promoted': 0}
    promote_candidates = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_case, c): c for c in cases}

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            stats['checked'] += 1
            stats[result['status']] = stats.get(result['status'], 0) + 1

            if result['status'] == 'promote':
                promote_candidates.append(result)
                logger.info(f"  FOUND: {result['case_number']} now has sale indicators!")

            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i+1}/{len(cases)} cases checked, {len(promote_candidates)} candidates found")

    # Promote candidates to main table
    if not dry_run:
        for candidate in promote_candidates:
            if promote_case_to_main(candidate):
                stats['promoted'] += 1

    logger.info(f"\n{'='*50}")
    logger.info(f"RE-EVALUATION COMPLETE")
    logger.info(f"{'='*50}")
    logger.info(f"  Cases checked: {stats['checked']}")
    logger.info(f"  Still skip: {stats['still_skip']}")
    logger.info(f"  Candidates found: {stats['promote']}")
    logger.info(f"  Promoted to main table: {stats['promoted']}")
    logger.info(f"  Errors: {stats['error']}")

    # Generate detailed report
    report_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'reevaluate_report.md')
    generate_report(stats, promote_candidates, report_path)

    return stats, promote_candidates


def generate_report(stats: dict, promoted_cases: list, report_path: str):
    """Generate a detailed markdown report of the reevaluation."""
    from datetime import datetime

    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, 'w') as f:
        f.write(f"# Dismissed Cases Re-evaluation Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write(f"## Summary\n\n")
        f.write(f"| Metric | Count |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Cases checked | {stats['checked']} |\n")
        f.write(f"| Still skipped (no indicators) | {stats.get('still_skip', 0)} |\n")
        f.write(f"| Candidates found | {stats.get('promote', 0)} |\n")
        f.write(f"| Successfully promoted | {stats.get('promoted', 0)} |\n")
        f.write(f"| Errors | {stats.get('error', 0)} |\n\n")

        if promoted_cases:
            f.write(f"## Promoted Cases\n\n")
            f.write(f"The following cases were promoted from `skipped_cases` to the main `cases` table:\n\n")
            f.write(f"| Case Number | County | File Date | Classification | Sale Date | Key Event |\n")
            f.write(f"|-------------|--------|-----------|----------------|-----------|----------|\n")

            for case in promoted_cases:
                case_info = case.get('case_info', {})
                case_data = case.get('case_data', {})
                sale_date = case.get('sale_date', '')

                # Find key sale event
                key_event = ''
                for event in case_data.get('events', []):
                    etype = (event.get('event_type') or '').lower()
                    if any(x in etype for x in ['report of sale', 'order for sale', 'partition', 'upset bid']):
                        key_event = event.get('event_type', '')[:40]
                        break

                # Determine classification
                if sale_date:
                    from common.business_days import calculate_upset_bid_deadline
                    deadline = calculate_upset_bid_deadline(sale_date)
                    classification = 'upset_bid' if deadline >= date.today() else 'closed_sold'
                else:
                    classification = 'upcoming'

                f.write(f"| {case_info.get('case_number', 'N/A')} | {case_info.get('county_name', 'N/A')} | {case_info.get('file_date', 'N/A')} | {classification} | {sale_date or 'N/A'} | {key_event} |\n")

            f.write(f"\n### Case Details\n\n")
            for case in promoted_cases:
                case_info = case.get('case_info', {})
                case_data = case.get('case_data', {})

                f.write(f"#### {case_info.get('case_number', 'Unknown')}\n\n")
                f.write(f"- **County:** {case_info.get('county_name', 'N/A')}\n")
                f.write(f"- **File Date:** {case_info.get('file_date', 'N/A')}\n")
                f.write(f"- **Case Type:** {case_data.get('case_type', 'N/A')}\n")
                f.write(f"- **Sale Date:** {case.get('sale_date', 'N/A')}\n")
                f.write(f"- **Events:** {len(case_data.get('events', []))}\n\n")

                # List relevant events
                f.write(f"**Key Events:**\n")
                for event in case_data.get('events', [])[:10]:
                    etype = event.get('event_type', '')
                    edate = event.get('event_date', '')
                    if etype:
                        f.write(f"- {edate}: {etype}\n")
                f.write(f"\n---\n\n")
        else:
            f.write(f"## No Cases Promoted\n\n")
            f.write(f"No dismissed cases were found to have new sale indicators.\n\n")

        f.write(f"## Next Steps\n\n")
        f.write(f"1. Review promoted cases in the dashboard\n")
        f.write(f"2. Run OCR/extraction on new cases if needed\n")
        f.write(f"3. Monitor for upcoming deadlines\n")

    logger.info(f"Report generated: {report_path}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Re-evaluate dismissed skipped cases')
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--limit', type=int, help='Limit number of cases to check')
    parser.add_argument('--dry-run', action='store_true', help='Check only, do not promote')
    args = parser.parse_args()

    run_reevaluation(max_workers=args.workers, limit=args.limit, dry_run=args.dry_run)
