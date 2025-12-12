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
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

# Enable new headless mode for Chromium - required for Angular apps to load
os.environ['PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW'] = '1'

from playwright.sync_api import sync_playwright, Browser, Page

from database.connection import get_session
from database.models import Case, CaseEvent
from scraper.page_parser import parse_case_detail
from scraper.pdf_downloader import download_upset_bid_documents, download_all_case_documents
from extraction.classifier import (
    SALE_REPORT_EVENTS,
    BLOCKING_EVENTS,
    UPSET_BID_EVENTS,
    classify_case,
    update_case_classification
)
from extraction.extractor import (
    extract_upset_bid_data, is_upset_bid_document,
    extract_report_of_sale_data, is_report_of_sale_document,
    update_case_with_extracted_data
)
from ocr.processor import extract_text_from_pdf
from common.logger import setup_logger
from common.county_codes import get_county_name
from common.business_days import calculate_upset_bid_deadline

logger = setup_logger(__name__)


class CaseMonitor:
    """Monitor existing cases for status updates."""

    def __init__(
        self,
        max_workers: int = 8,
        headless: bool = False,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize case monitor.

        Args:
            max_workers: Number of parallel browser instances
            headless: Run browsers in headless mode (default: False for reliability)
            max_retries: Maximum retry attempts per case for transient failures
            retry_delay: Initial delay between retries (doubles with each retry)
        """
        self.max_workers = max_workers
        self.headless = headless
        self.max_retries = max_retries
        self.retry_delay = retry_delay
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

    def fetch_case_page(
        self,
        page: Page,
        case_url: str,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> Optional[str]:
        """
        Fetch a case detail page with retry logic for transient failures.

        Args:
            page: Playwright page object
            case_url: URL to fetch
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (doubles each retry)

        Returns:
            HTML content or None on error
        """
        import time

        last_error = None
        delay = retry_delay

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"  Retry attempt {attempt}/{max_retries} after {delay:.1f}s delay...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff

                # Clear Angular SPA state by navigating to about:blank first
                # This ensures we get fresh content, not cached from previous case
                page.goto('about:blank', wait_until='domcontentloaded', timeout=5000)

                # Navigate to the case page
                page.goto(case_url, wait_until='networkidle', timeout=30000)

                # Wait for Angular app to fully load - the ROA app takes time to render
                # The roa-caseinfo-info-rows table contains case type/status and appears when data loads
                try:
                    page.wait_for_selector('table.roa-caseinfo-info-rows', state='visible', timeout=15000)
                except:
                    # Fallback: wait a fixed time for Angular to render
                    time.sleep(5)

                content = page.content()

                # Verify we got valid content with actual case data
                # Must have the ROA table which indicates Angular has rendered the case data
                # Note: HTML uses &nbsp; so we check for "roa-label" class which appears in rendered data
                if (content and
                    len(content) > 1000 and
                    'roa-caseinfo-info-rows' in content and
                    'roa-label' in content):
                    if attempt > 0:
                        logger.info(f"  Successfully fetched on retry {attempt}")
                    return content
                else:
                    raise Exception("Page loaded but case data table not found (Angular not fully rendered)")

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"  Attempt {attempt + 1} failed: {e}")
                else:
                    logger.error(f"  All {max_retries + 1} attempts failed for {case_url}: {e}")

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
            sig = (e.get('event_date'), (e.get('event_type') or '').strip().lower())
            existing_signatures.add(sig)

        for event in parsed_events:
            sig = (event.get('event_date'), (event.get('event_type') or '').strip().lower())
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

                # Calculate new deadline (10 days from bid date, adjusted for weekends/holidays)
                if event_date:
                    try:
                        bid_date = datetime.strptime(event_date, '%m/%d/%Y').date()
                        adjusted_deadline = calculate_upset_bid_deadline(bid_date)
                        case.next_bid_deadline = datetime.combine(adjusted_deadline, datetime.min.time())
                    except:
                        pass

                case.updated_at = datetime.utcnow()
                session.commit()

                logger.info(f"  Updated bid: ${old_bid} -> ${new_bid_amount}, "
                           f"min next: ${case.minimum_next_bid}, deadline: {case.next_bid_deadline}")

    def extract_bid_from_documents(
        self,
        page: Page,
        case: Case,
        html_bid: Optional[Decimal] = None
    ) -> Optional[Dict]:
        """
        Download ALL case documents, OCR them, and extract bid data from upset bid forms.

        This function:
        1. Downloads ALL documents for the case (for complete AI analysis context)
        2. Runs OCR on downloaded PDFs
        3. For upset bid documents (AOC-SP-403), extracts structured bid data
        4. Optionally verifies against HTML-extracted bid amount

        By downloading ALL documents, we ensure the AI analysis has full context
        including mortgage amounts, deed info, attorney details, etc.

        Args:
            page: Playwright page object (on case detail page)
            case: Case object
            html_bid: Optional bid amount extracted from HTML (for verification)

        Returns:
            Dict with extracted bid data, or None if extraction failed:
                - current_bid: Decimal bid amount
                - previous_bid: Decimal previous bid amount
                - minimum_next_bid: Decimal minimum for next bid
                - deposit_required: Decimal deposit amount
                - source: 'pdf' or 'html'
                - verified: True if HTML and PDF match
                - total_docs_downloaded: Count of all documents downloaded
                - event_date: Date of the event (for logging only, NOT used for deadline)

            NOTE: next_deadline is NOT included - deadlines are always calculated
            from event dates using calculate_upset_bid_deadline(), not from PDF OCR.
        """
        # Get county name from case number (format: YYSPXXXXXX-CCC)
        county_code = case.case_number.split('-')[-1] if '-' in case.case_number else None
        county_name = get_county_name(county_code) if county_code else 'unknown'

        # Download ALL documents for the case (for complete AI analysis)
        # This ensures we have mortgage info, deed details, etc.
        downloaded = download_all_case_documents(
            page, case.id, county_name, case.case_number,
            skip_existing=True  # Don't re-download documents we already have
        )

        if not downloaded:
            logger.debug(f"  No documents to download")
            return None

        # Count new downloads for reporting
        new_docs = sum(1 for d in downloaded if d.get('is_new'))
        logger.info(f"  Downloaded {new_docs} new documents, {len(downloaded) - new_docs} already existed")

        best_bid_data = None
        report_of_sale_data = None  # Track Report of Sale data separately

        # Sort documents by event_date in REVERSE chronological order (newest first)
        # This ensures we process the most recent upset bid documents first
        # and don't overwrite with stale data from older PDFs
        def parse_event_date(doc_info):
            """Parse event_date string to datetime for sorting, None sorts last."""
            event_date = doc_info.get('event_date')
            if event_date:
                try:
                    return datetime.strptime(event_date, '%m/%d/%Y')
                except:
                    pass
            return datetime.min  # Documents without dates sort to the end

        sorted_docs = sorted(downloaded, key=parse_event_date, reverse=True)

        # Process documents for bid extraction (focus on upset bid/sale docs)
        for doc_info in sorted_docs:
            # Skip if not a new download and we don't need to re-OCR
            if not doc_info.get('is_new') and not doc_info.get('is_upset_bid') and not doc_info.get('is_sale'):
                continue

            file_path = doc_info.get('file_path')
            if not file_path:
                continue

            # Only OCR upset bid and sale documents for bid extraction
            if not (doc_info.get('is_upset_bid') or doc_info.get('is_sale')):
                continue

            # Run OCR on the document
            logger.info(f"  OCR processing: {doc_info.get('event_type', 'document')}")
            ocr_text, method = extract_text_from_pdf(file_path)

            if not ocr_text:
                logger.warning(f"    No text extracted from {file_path}")
                continue

            # Save OCR text to database
            doc_id = doc_info.get('document_id')
            if doc_id and ocr_text:
                with get_session() as sess:
                    from database.models import Document
                    doc_record = sess.query(Document).filter_by(id=doc_id).first()
                    if doc_record and not doc_record.ocr_text:
                        doc_record.ocr_text = ocr_text
                        sess.commit()
                        logger.debug(f"    Saved {len(ocr_text)} chars of OCR text to database")
                    elif doc_record and doc_record.ocr_text:
                        logger.debug(f"    OCR text already exists in database")

            # Check if this is a Report of Sale document (AOC-SP-301)
            # This contains the INITIAL bid from the auction
            if is_report_of_sale_document(ocr_text):
                logger.info(f"    Detected AOC-SP-301 (Report of Foreclosure Sale) form")

                # Extract Report of Sale data
                ros_data = extract_report_of_sale_data(ocr_text)

                if ros_data.get('initial_bid'):
                    logger.info(f"    Extracted initial bid from auction: ${ros_data['initial_bid']}")

                    # Convert to standard bid_data format
                    # NOTE: We do NOT include next_deadline from PDF - it will be calculated
                    # from event dates using calculate_upset_bid_deadline()
                    report_of_sale_data = {
                        'current_bid': ros_data['initial_bid'],
                        'previous_bid': None,  # No previous bid - this is the first
                        'minimum_next_bid': round(ros_data['initial_bid'] * Decimal('1.05'), 2),
                        'deposit_required': None,
                        'source': 'pdf_report_of_sale',
                        'document_path': file_path,
                        'event_type': doc_info.get('event_type'),
                        'event_date': doc_info.get('event_date'),
                        'sale_date': ros_data.get('sale_date'),
                        'verified': False,
                    }

            # Check if this is an upset bid document (AOC-SP-403)
            # This contains subsequent upset bids (higher than Report of Sale bid)
            elif is_upset_bid_document(ocr_text):
                logger.info(f"    Detected AOC-SP-403 (Notice of Upset Bid) form")

                # Extract structured bid data
                bid_data = extract_upset_bid_data(ocr_text)

                if bid_data.get('current_bid'):
                    logger.info(f"    Extracted upset bid: ${bid_data['current_bid']}")

                    # Add metadata
                    bid_data['source'] = 'pdf_upset_bid'
                    bid_data['document_path'] = file_path
                    bid_data['event_type'] = doc_info.get('event_type')
                    bid_data['event_date'] = doc_info.get('event_date')
                    bid_data['total_docs_downloaded'] = len(downloaded)

                    # Verify against HTML bid if available
                    if html_bid:
                        if html_bid == bid_data['current_bid']:
                            bid_data['verified'] = True
                            logger.info(f"    Bid VERIFIED: HTML and PDF match (${html_bid})")
                        else:
                            bid_data['verified'] = False
                            logger.warning(f"    Bid MISMATCH: HTML=${html_bid}, PDF=${bid_data['current_bid']}")
                    else:
                        bid_data['verified'] = False

                    # Keep the FIRST upset bid data we find (documents are sorted newest first)
                    # This ensures we use the most recent upset bid, not the highest amount
                    # (older PDFs may have OCR errors that extract incorrectly high amounts)
                    if not best_bid_data:
                        best_bid_data = bid_data
                        logger.info(f"    Using upset bid from {doc_info.get('event_date', 'unknown')} as most recent")
                    else:
                        logger.debug(f"    Skipping older upset bid from {doc_info.get('event_date', 'unknown')}")

        # Decide which data to return:
        # 1. If we have upset bid data, use that (it's the most recent bid - documents sorted newest first)
        # 2. If we only have Report of Sale data, use that (initial bid from auction)
        # 3. If neither, return None
        if best_bid_data:
            best_bid_data['total_docs_downloaded'] = len(downloaded)
            # If we also found report of sale, note the initial bid for reference
            if report_of_sale_data:
                best_bid_data['initial_auction_bid'] = report_of_sale_data.get('current_bid')
            return best_bid_data
        elif report_of_sale_data:
            report_of_sale_data['total_docs_downloaded'] = len(downloaded)
            logger.info(f"    Using Report of Sale as bid source (no upset bids filed yet)")
            return report_of_sale_data

        return None

    def update_case_with_pdf_bid_data(self, case_id: int, bid_data: Dict) -> bool:
        """
        Update case with bid data extracted from PDF documents.

        This updates the case with accurate bid information from:
        - AOC-SP-301 (Report of Foreclosure Sale): Initial bid from auction
        - AOC-SP-403 (Notice of Upset Bid): Subsequent upset bids

        Fields updated:
        - current_bid_amount: The current highest bid
        - minimum_next_bid: Calculated 5% above current (from PDF or calculated)
        - sale_date: Date of the auction sale (from Report of Sale)

        NOTE: next_bid_deadline is NOT updated from PDF data - it is ALWAYS calculated
        from the most recent "Upset Bid Filed" event date using business day logic.

        Args:
            case_id: Database ID of the case
            bid_data: Dict with extracted bid data from extract_bid_from_documents()

        Returns:
            True if update was successful
        """
        if not bid_data or not bid_data.get('current_bid'):
            return False

        with get_session() as session:
            case = session.query(Case).filter_by(id=case_id).first()
            if not case:
                return False

            old_bid = case.current_bid_amount

            # Update bid amount
            case.current_bid_amount = bid_data['current_bid']

            # Use PDF minimum if available, otherwise calculate
            if bid_data.get('minimum_next_bid'):
                case.minimum_next_bid = bid_data['minimum_next_bid']
            else:
                case.minimum_next_bid = round(bid_data['current_bid'] * Decimal('1.05'), 2)

            # Calculate deadline from the most recent "Upset Bid Filed" event date
            # This ensures the deadline is always based on actual event dates, not PDF OCR
            # which may have stale data or OCR errors
            # Query within the existing session to avoid detached object issues
            recent_upset = session.query(CaseEvent).filter(
                CaseEvent.case_id == case_id,
                CaseEvent.event_type.ilike('%upset bid filed%'),
                CaseEvent.event_date.isnot(None)
            ).order_by(CaseEvent.event_date.desc()).first()

            if recent_upset and recent_upset.event_date:
                adjusted_deadline = calculate_upset_bid_deadline(recent_upset.event_date)
                case.next_bid_deadline = datetime.combine(adjusted_deadline, datetime.min.time())
                logger.debug(f"  Calculated deadline from event {recent_upset.event_date}: {adjusted_deadline}")

            # Update sale_date if available (from Report of Sale)
            if bid_data.get('sale_date') and not case.sale_date:
                case.sale_date = bid_data['sale_date']

            case.updated_at = datetime.now(timezone.utc)
            session.commit()

            source_type = bid_data.get('source', 'pdf')
            logger.info(f"  Updated bid from {source_type}: ${old_bid} -> ${bid_data['current_bid']}, "
                       f"min next: ${case.minimum_next_bid}, deadline: {case.next_bid_deadline}")

            return True

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
            'pdf_bid_extracted': False,
            'error': None
        }

        try:
            logger.info(f"Checking case {case.case_number} ({case.classification})")

            # Fetch the case page with retry logic
            html = self.fetch_case_page(
                page,
                case.case_url,
                max_retries=self.max_retries,
                retry_delay=self.retry_delay
            )
            if not html:
                result['error'] = f"Failed to fetch page after {self.max_retries + 1} attempts"
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
                        # Get the actual event date from database, not HTML parse
                        # HTML-parsed party events often have NULL dates
                        with get_session() as session:
                            latest_upset = session.query(CaseEvent).filter(
                                CaseEvent.case_id == case.id,
                                CaseEvent.event_type.ilike('%upset bid filed%'),
                                CaseEvent.event_date.isnot(None)
                            ).order_by(CaseEvent.event_date.desc()).first()

                            if latest_upset and latest_upset.event_date:
                                event_date_str = latest_upset.event_date.strftime('%m/%d/%Y')
                            else:
                                event_date_str = None

                        bid_amount = self.extract_bid_amount(html)
                        if bid_amount:
                            self.update_case_bid_info(case.id, bid_amount, event_date_str)
                            result['bid_updated'] = True

                    # Check for sale event on upcoming case -> will trigger reclassification
                    if self.is_sale_event(event_type) and case.classification == 'upcoming':
                        logger.info(f"  Sale event detected on upcoming case")
                        # Store deadline from sale date
                        try:
                            event_date_str = event.get('event_date')
                            if event_date_str:
                                event_date = datetime.strptime(event_date_str, '%m/%d/%Y').date()
                                from common.business_days import calculate_upset_bid_deadline
                                deadline = calculate_upset_bid_deadline(event_date)
                                with get_session() as sess:
                                    case_obj = sess.query(Case).filter_by(id=case.id).first()
                                    if case_obj:
                                        case_obj.next_bid_deadline = datetime.combine(deadline, datetime.min.time())
                                        case_obj.sale_date = event_date
                                        sess.commit()
                                        logger.info(f"  Set deadline to {deadline} from sale date {event_date}")
                        except Exception as e:
                            logger.warning(f"  Failed to set deadline from sale event: {e}")

                    # Check for blocking event
                    if self.is_blocking_event(event_type):
                        logger.info(f"  Blocking event detected")

            # For upset_bid cases missing bid amount, try to extract from page
            # This handles cases that were already classified but never had bid extracted
            if case.classification == 'upset_bid' and not case.current_bid_amount:
                bid_amount = self.extract_bid_amount(html)
                if bid_amount:
                    # Find the most recent upset bid or sale event date for deadline calculation
                    event_date = None
                    for event in parsed_events:
                        evt_type = (event.get('event_type') or '').lower()
                        if 'upset' in evt_type or 'sale' in evt_type:
                            event_date = event.get('event_date')
                            break
                    self.update_case_bid_info(case.id, bid_amount, event_date)
                    result['bid_updated'] = True
                    logger.info(f"  Extracted missing bid amount: ${bid_amount}")

            # Check if this case has upset bid activity (either classified or has events)
            has_upset_events = any(
                self.is_upset_bid_event(e.get('event_type', ''))
                for e in case_data.get('events', [])
            )

            # For upset_bid cases OR cases with upset bid events, try to extract bid data from PDF documents
            # PDFs (AOC-SP-403 forms) contain more accurate/complete bid information
            # This ensures misclassified cases still get their PDFs processed for accurate deadlines
            if case.classification == 'upset_bid' or has_upset_events:
                # Get HTML bid for verification
                html_bid = self.extract_bid_amount(html) if not case.current_bid_amount else case.current_bid_amount

                try:
                    pdf_bid_data = self.extract_bid_from_documents(page, case, html_bid)
                    if pdf_bid_data and pdf_bid_data.get('current_bid'):
                        # Update case with PDF data (more accurate than HTML)
                        if self.update_case_with_pdf_bid_data(case.id, pdf_bid_data):
                            result['bid_updated'] = True
                            result['pdf_bid_extracted'] = True
                            if pdf_bid_data.get('verified'):
                                logger.info(f"  Bid verified: HTML and PDF match")
                except Exception as e:
                    logger.warning(f"  PDF bid extraction failed (non-blocking): {e}")

            # Reclassify the case based on current events
            # Only change classification if the new one is valid (not None)
            # This prevents losing existing classifications due to parsing issues
            old_classification = case.classification
            new_classification = update_case_classification(case.id)

            # Run full extraction to populate any missing fields from new documents
            extraction_updated = update_case_with_extracted_data(case.id)
            if extraction_updated:
                logger.info(f"  Extraction updated case data")
                result['extraction_updated'] = True

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
                # Use a real Chrome user-agent to avoid bot detection
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
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
    max_workers: int = 8,
    headless: bool = False,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> Dict:
    """
    Convenience function to monitor cases.

    Args:
        classification: Filter by classification (upcoming, blocked, upset_bid)
        limit: Maximum number of cases to check
        dry_run: If True, just count cases
        max_workers: Number of parallel browsers (default: 8)
        headless: Run in headless mode (default: False for reliability)
        max_retries: Max retry attempts per case (default: 3)
        retry_delay: Initial delay between retries in seconds (default: 2.0)

    Returns:
        Dict with monitoring results
    """
    monitor = CaseMonitor(
        max_workers=max_workers,
        headless=headless,
        max_retries=max_retries,
        retry_delay=retry_delay
    )

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
    parser.add_argument('--headless', action='store_true',
                       help='Run in headless mode (default: visible browser)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Max retry attempts per case (default: 3)')
    parser.add_argument('--retry-delay', type=float, default=2.0,
                       help='Initial delay between retries in seconds (default: 2.0)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without processing')

    args = parser.parse_args()

    results = monitor_cases(
        classification=args.classification,
        limit=args.limit,
        dry_run=args.dry_run,
        max_workers=args.workers,
        headless=args.headless,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay
    )

    print(f"\nResults: {results}")
