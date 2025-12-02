"""Case monitoring module - checks existing cases for status updates.

This module visits case URLs directly (no CAPTCHA needed) to detect:
- New events (sale reports, upset bids, bankruptcy filings)
- Status changes that affect classification

Usage:
    from scraper.case_monitor import CaseMonitor
    monitor = CaseMonitor()
    results = monitor.run()
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

# Enable new headless mode for Chromium - required for Angular apps to load
os.environ['PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW'] = '1'

from playwright.sync_api import sync_playwright, Browser, Page

from database.connection import get_session
from database.models import Case, CaseEvent
from scraper.page_parser import parse_case_detail
from extraction.classifier import (
    SALE_REPORT_EVENTS,
    BLOCKING_EVENTS,
    UPSET_BID_EVENTS,
    classify_case,
    update_case_classification
)
from common.logger import setup_logger

logger = setup_logger(__name__)


class CaseMonitor:
    """Monitor existing cases for status updates."""

    def __init__(self, max_workers: int = 8, headless: bool = True):
        """
        Initialize case monitor.

        Args:
            max_workers: Number of parallel browser instances
            headless: Run browsers in headless mode (uses new headless mode for Angular compatibility)
        """
        self.max_workers = max_workers
        self.headless = headless
        self.results = {
            'cases_checked': 0,
            'events_added': 0,
            'classifications_changed': 0,
            'bid_updates': 0,
            'errors': []
        }

    def get_cases_to_monitor(self) -> List[Case]:
        """
        Get all cases that need monitoring.

        Returns:
            List of Case objects with classification in ('upcoming', 'blocked', 'upset_bid')
        """
        with get_session() as session:
            cases = session.query(Case).filter(
                Case.classification.in_(['upcoming', 'blocked', 'upset_bid']),
                Case.case_url.isnot(None)
            ).all()

            # Detach from session
            session.expunge_all()
            return cases

    def get_existing_events(self, case_id: int) -> List[Dict]:
        """
        Get existing events for a case to compare against.

        Args:
            case_id: Database ID of the case

        Returns:
            List of event dicts with event_date and event_type
        """
        with get_session() as session:
            events = session.query(CaseEvent).filter_by(case_id=case_id).all()
            return [
                {
                    'event_date': e.event_date.strftime('%m/%d/%Y') if e.event_date else None,
                    'event_type': e.event_type
                }
                for e in events
            ]

    def fetch_case_page(self, page: Page, case_url: str) -> Optional[str]:
        """
        Fetch a case detail page.

        Args:
            page: Playwright page object
            case_url: URL to fetch

        Returns:
            HTML content or None on error
        """
        try:
            page.goto(case_url, wait_until='networkidle', timeout=30000)

            # Wait for Angular app to fully load - the ROA app takes time to render
            # First wait for any content indicator
            try:
                # Wait for the Case Information heading which appears after Angular loads
                page.wait_for_selector('h1:has-text("Case Information")', state='visible', timeout=10000)
            except:
                # Fallback: wait a fixed time for Angular to render
                import time
                time.sleep(5)

            return page.content()

        except Exception as e:
            logger.error(f"Error fetching {case_url}: {e}")
            return None

    def detect_new_events(
        self,
        existing_events: List[Dict],
        parsed_events: List[Dict]
    ) -> List[Dict]:
        """
        Compare parsed events against existing to find new ones.

        Args:
            existing_events: Events already in database
            parsed_events: Events parsed from current page

        Returns:
            List of new events not in database
        """
        new_events = []

        # Create set of existing event signatures for comparison
        existing_signatures = set()
        for e in existing_events:
            sig = (e.get('event_date'), (e.get('event_type') or '').lower())
            existing_signatures.add(sig)

        for event in parsed_events:
            sig = (event.get('event_date'), (event.get('event_type') or '').lower())
            if sig not in existing_signatures and event.get('event_type'):
                new_events.append(event)

        return new_events

    def is_sale_event(self, event_type: str) -> bool:
        """Check if event type indicates a sale occurred."""
        if not event_type:
            return False
        event_lower = event_type.lower()
        return any(sale in event_lower for sale in SALE_REPORT_EVENTS)

    def is_upset_bid_event(self, event_type: str) -> bool:
        """Check if event type indicates an upset bid was filed."""
        if not event_type:
            return False
        event_lower = event_type.lower()
        return any(upset in event_lower for upset in UPSET_BID_EVENTS)

    def is_blocking_event(self, event_type: str) -> bool:
        """Check if event type indicates a blocking event (bankruptcy, stay)."""
        if not event_type:
            return False
        event_lower = event_type.lower()
        return any(block in event_lower for block in BLOCKING_EVENTS)

    def extract_bid_amount(self, page_text: str) -> Optional[Decimal]:
        """
        Extract bid amount from page text.

        Looks for patterns like:
        - $123,456.78
        - Bid Amount: $123,456.78
        - Sale Price: $123,456.78

        Args:
            page_text: Full text of the case page

        Returns:
            Decimal bid amount or None
        """
        # Pattern for currency amounts
        patterns = [
            r'(?:bid|sale|price|amount)[^\$]*\$\s*([\d,]+(?:\.\d{2})?)',
            r'\$\s*([\d,]+(?:\.\d{2})?)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                # Take the largest amount found (likely the bid)
                amounts = []
                for match in matches:
                    try:
                        amount = Decimal(match.replace(',', ''))
                        if amount > 1000:  # Filter out small amounts
                            amounts.append(amount)
                    except:
                        pass
                if amounts:
                    return max(amounts)

        return None

    def update_case_bid_info(
        self,
        case_id: int,
        new_bid_amount: Decimal,
        event_date: Optional[str] = None
    ):
        """
        Update case with new bid information.

        Args:
            case_id: Database ID of the case
            new_bid_amount: New bid amount
            event_date: Date of the bid event (for calculating deadline)
        """
        with get_session() as session:
            case = session.query(Case).filter_by(id=case_id).first()
            if case:
                old_bid = case.current_bid_amount

                case.current_bid_amount = new_bid_amount
                case.minimum_next_bid = round(new_bid_amount * Decimal('1.05'), 2)

                # Calculate new deadline (10 days from bid date)
                if event_date:
                    try:
                        bid_date = datetime.strptime(event_date, '%m/%d/%Y')
                        case.next_bid_deadline = bid_date + timedelta(days=10)
                    except:
                        pass

                case.updated_at = datetime.utcnow()
                session.commit()

                logger.info(f"  Updated bid: ${old_bid} -> ${new_bid_amount}, "
                           f"min next: ${case.minimum_next_bid}, deadline: {case.next_bid_deadline}")

    def add_new_events(self, case_id: int, new_events: List[Dict]):
        """
        Add new events to the database.

        Args:
            case_id: Database ID of the case
            new_events: List of event dicts to add
        """
        with get_session() as session:
            for event_data in new_events:
                # Parse event date
                event_date = None
                if event_data.get('event_date'):
                    try:
                        event_date = datetime.strptime(event_data['event_date'], '%m/%d/%Y').date()
                    except:
                        pass

                event = CaseEvent(
                    case_id=case_id,
                    event_date=event_date,
                    event_type=event_data.get('event_type'),
                    filed_by=event_data.get('filed_by'),
                    filed_against=event_data.get('filed_against'),
                    document_url=event_data.get('document_url')
                )
                session.add(event)

            session.commit()

    def process_case(self, case: Case, page: Page) -> Dict:
        """
        Process a single case for updates.

        Args:
            case: Case object to check
            page: Playwright page object

        Returns:
            Dict with processing results
        """
        result = {
            'case_number': case.case_number,
            'events_added': 0,
            'classification_changed': False,
            'bid_updated': False,
            'error': None
        }

        try:
            logger.info(f"Checking case {case.case_number} ({case.classification})")

            # Fetch the case page
            html = self.fetch_case_page(page, case.case_url)
            if not html:
                result['error'] = "Failed to fetch page"
                return result

            # Parse the page
            case_data = parse_case_detail(html)
            parsed_events = case_data.get('events', [])

            # Get existing events
            existing_events = self.get_existing_events(case.id)

            # Find new events
            new_events = self.detect_new_events(existing_events, parsed_events)

            if new_events:
                logger.info(f"  Found {len(new_events)} new events")
                for event in new_events:
                    logger.info(f"    - {event.get('event_date')}: {event.get('event_type')}")

                # Add new events to database
                self.add_new_events(case.id, new_events)
                result['events_added'] = len(new_events)

                # Check for specific event types that need special handling
                for event in new_events:
                    event_type = event.get('event_type', '')

                    # Check for upset bid -> update bid amounts
                    if self.is_upset_bid_event(event_type):
                        bid_amount = self.extract_bid_amount(html)
                        if bid_amount:
                            self.update_case_bid_info(case.id, bid_amount, event.get('event_date'))
                            result['bid_updated'] = True

                    # Check for sale event on upcoming case -> will trigger reclassification
                    if self.is_sale_event(event_type) and case.classification == 'upcoming':
                        logger.info(f"  Sale event detected on upcoming case")

                    # Check for blocking event
                    if self.is_blocking_event(event_type):
                        logger.info(f"  Blocking event detected")

            # Reclassify the case based on current events
            # Only change classification if the new one is valid (not None)
            # This prevents losing existing classifications due to parsing issues
            old_classification = case.classification
            new_classification = update_case_classification(case.id)

            if new_classification and old_classification != new_classification:
                logger.info(f"  Classification changed: {old_classification} -> {new_classification}")
                result['classification_changed'] = True
            elif new_classification is None and old_classification:
                # Restore the original classification - don't lose it
                with get_session() as session:
                    db_case = session.query(Case).filter_by(id=case.id).first()
                    if db_case:
                        db_case.classification = old_classification
                        session.commit()
                logger.debug(f"  Preserved classification: {old_classification} (classifier returned None)")

            # Update last_scraped_at timestamp
            with get_session() as session:
                db_case = session.query(Case).filter_by(id=case.id).first()
                if db_case:
                    db_case.last_scraped_at = datetime.now(timezone.utc)
                    session.commit()

        except Exception as e:
            logger.error(f"  Error processing case {case.case_number}: {e}")
            result['error'] = str(e)

        return result

    def _process_case_batch(self, cases: List[Case], worker_id: int) -> List[Dict]:
        """
        Process a batch of cases in a single browser instance.

        Args:
            cases: List of cases to process
            worker_id: Worker identifier for logging

        Returns:
            List of result dicts for each case
        """
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            try:
                context = browser.new_context()
                page = context.new_page()

                for i, case in enumerate(cases):
                    logger.debug(f"[Worker {worker_id}] Processing case {i+1}/{len(cases)}: {case.case_number}")
                    result = self.process_case(case, page)
                    results.append(result)

            finally:
                browser.close()

        return results

    def run(self, cases: List[Case] = None, dry_run: bool = False) -> Dict:
        """
        Run the case monitor with parallel browser support.

        Args:
            cases: Optional list of cases to check (default: all monitored cases)
            dry_run: If True, just count cases without processing

        Returns:
            Dict with monitoring results
        """
        if cases is None:
            cases = self.get_cases_to_monitor()

        logger.info(f"Monitoring {len(cases)} cases with {self.max_workers} parallel browsers")

        if dry_run:
            logger.info("[DRY RUN] Would check the following cases:")
            by_classification = {}
            for case in cases:
                cls = case.classification or 'unknown'
                by_classification[cls] = by_classification.get(cls, 0) + 1

            for cls, count in sorted(by_classification.items()):
                logger.info(f"  {cls}: {count} cases")

            return {'cases_to_check': len(cases), 'dry_run': True}

        # Split cases into batches for parallel processing
        batch_size = max(1, len(cases) // self.max_workers)
        batches = []
        for i in range(0, len(cases), batch_size):
            batches.append(cases[i:i + batch_size])

        # Limit to max_workers batches (redistribute if we have more)
        while len(batches) > self.max_workers:
            # Merge last batch into second-to-last
            batches[-2].extend(batches[-1])
            batches.pop()

        logger.info(f"Split into {len(batches)} batches: {[len(b) for b in batches]}")

        # Process batches in parallel
        all_results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_case_batch, batch, i): i
                for i, batch in enumerate(batches)
            }

            for future in as_completed(futures):
                worker_id = futures[future]
                try:
                    batch_results = future.result()
                    all_results.extend(batch_results)
                    logger.info(f"[Worker {worker_id}] Completed {len(batch_results)} cases")
                except Exception as e:
                    logger.error(f"[Worker {worker_id}] Failed: {e}")
                    self.results['errors'].append(f"Worker {worker_id} failed: {e}")

        # Aggregate results
        for result in all_results:
            self.results['cases_checked'] += 1
            self.results['events_added'] += result['events_added']

            if result['classification_changed']:
                self.results['classifications_changed'] += 1
            if result['bid_updated']:
                self.results['bid_updates'] += 1
            if result['error']:
                self.results['errors'].append(f"{result['case_number']}: {result['error']}")

        # Summary
        logger.info("=" * 50)
        logger.info("MONITORING COMPLETE")
        logger.info("=" * 50)
        logger.info(f"  Cases checked: {self.results['cases_checked']}")
        logger.info(f"  New events added: {self.results['events_added']}")
        logger.info(f"  Classifications changed: {self.results['classifications_changed']}")
        logger.info(f"  Bid updates: {self.results['bid_updates']}")
        logger.info(f"  Errors: {len(self.results['errors'])}")

        return self.results


def monitor_cases(
    classification: str = None,
    limit: int = None,
    dry_run: bool = False,
    max_workers: int = 8
) -> Dict:
    """
    Convenience function to monitor cases.

    Args:
        classification: Filter by classification (upcoming, blocked, upset_bid)
        limit: Maximum number of cases to check
        dry_run: If True, just count cases
        max_workers: Number of parallel browsers (default: 4)

    Returns:
        Dict with monitoring results
    """
    monitor = CaseMonitor(max_workers=max_workers)

    with get_session() as session:
        query = session.query(Case).filter(
            Case.case_url.isnot(None)
        )

        if classification:
            query = query.filter(Case.classification == classification)
        else:
            query = query.filter(
                Case.classification.in_(['upcoming', 'blocked', 'upset_bid'])
            )

        if limit:
            query = query.limit(limit)

        cases = query.all()
        session.expunge_all()

    return monitor.run(cases=cases, dry_run=dry_run)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Monitor existing cases for updates')
    parser.add_argument('--classification', '-c',
                       choices=['upcoming', 'blocked', 'upset_bid'],
                       help='Filter by classification')
    parser.add_argument('--limit', '-l', type=int,
                       help='Maximum number of cases to check')
    parser.add_argument('--workers', '-w', type=int, default=8,
                       help='Number of parallel browsers (default: 8)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without processing')

    args = parser.parse_args()

    results = monitor_cases(
        classification=args.classification,
        limit=args.limit,
        dry_run=args.dry_run,
        max_workers=args.workers
    )

    print(f"\nResults: {results}")
