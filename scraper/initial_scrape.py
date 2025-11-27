"""Initial scrape to populate database with historical foreclosure data."""

import argparse
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from database.connection import get_session
from database.models import Case, CaseEvent, Party, Hearing, ScrapeLog
from scraper.vpn_manager import verify_vpn_or_exit
from scraper.captcha_solver import solve_recaptcha
from scraper.page_parser import is_foreclosure_case, parse_search_results, parse_case_detail, extract_total_count
from scraper.portal_interactions import (
    click_advanced_filter,
    fill_search_form as fill_portal_form,
    solve_and_submit_captcha,
    check_for_error,
    extract_total_count_from_page,
    go_to_next_page as navigate_next_page
)
from scraper.portal_selectors import PORTAL_URL
from scraper.pdf_downloader import download_case_documents
from common.county_codes import get_county_code, get_search_text, is_valid_county
from common.config import config
from common.logger import setup_logger

logger = setup_logger(__name__)


class TruncatedResultsError(Exception):
    """Raised when search results are truncated by the portal.

    This happens when the portal hits a result limit and shows a warning like:
    "The search returned XXX cases, but could have returned more.
     Please narrow the search by entering more precise criteria."

    The solution is to narrow the date range:
    - quarterly -> bi-monthly
    - bi-monthly -> monthly
    """
    pass


class InitialScraper:
    """Initial scraper for NC Courts Portal."""

    def __init__(self, county, start_date, end_date, test_mode=False, limit=None):
        """
        Initialize scraper.

        Args:
            county: County name (e.g., 'wake')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            test_mode: If True, limit scraping for testing
            limit: Maximum number of cases to process (for testing)
        """
        self.county = county.lower()
        self.county_code = get_county_code(self.county)
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        self.test_mode = test_mode
        self.limit = limit

        if not self.county_code:
            raise ValueError(f"Invalid county: {county}")

        logger.info(f"Scraper initialized for {self.county.title()} County ({self.county_code})")
        logger.info(f"Date range: {self.start_date} to {self.end_date}")
        if test_mode:
            logger.info(f"TEST MODE - Limit: {limit} cases")

    def run(self):
        """Execute the scraping process."""
        logger.info("=" * 60)
        logger.info("STARTING INITIAL SCRAPE")
        logger.info("=" * 60)

        # Step 1: Verify VPN (with auto-start if configured)
        verify_vpn_or_exit(
            auto_start=config.VPN_AUTO_START,
            sudo_password=config.SUDO_PASSWORD
        )

        # Step 2: Create scrape log
        scrape_log_id = self._create_scrape_log()
        cases_processed = 0
        status = 'failed'
        error_message = None
        cases_found = 0

        try:
            # Step 3: Launch browser and scrape
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)  # headless=False for development
                # Create a context so we can open new tabs for case details
                context = browser.new_context()
                page = context.new_page()

                try:
                    result = self._scrape_cases(page)
                    cases_processed = result['cases_processed']
                    cases_found = result['cases_found']
                    status = 'success'
                    logger.info(f"✓ Scrape completed successfully: {cases_processed} cases processed")

                except Exception as e:
                    logger.error(f"Scrape failed: {e}", exc_info=True)
                    status = 'failed'
                    error_message = str(e)
                    raise

                finally:
                    context.close()
                    browser.close()

        finally:
            # Update scrape log
            self._complete_scrape_log(scrape_log_id, cases_processed, cases_found, status, error_message)

        return scrape_log_id

    def _create_scrape_log(self):
        """Create initial scrape log entry."""
        with get_session() as session:
            scrape_log = ScrapeLog(
                scrape_type='initial',
                county_code=self.county_code,
                start_date=self.start_date,
                end_date=self.end_date,
                cases_found=0,
                cases_processed=0,
                status='running'
            )
            session.add(scrape_log)
            session.commit()
            session.refresh(scrape_log)
            # Store the ID to track this log
            self.scrape_log_id = scrape_log.id

        logger.info(f"Created scrape log (ID: {self.scrape_log_id})")
        return self.scrape_log_id

    def _complete_scrape_log(self, scrape_log_id, cases_processed, cases_found, status, error_message):
        """Update scrape log with final status."""
        with get_session() as session:
            log = session.query(ScrapeLog).filter_by(id=scrape_log_id).first()
            if log:
                log.completed_at = datetime.now()
                log.status = status
                log.cases_processed = cases_processed
                log.cases_found = cases_found
                log.error_message = error_message
                session.commit()

    def _scrape_cases(self, page):
        """
        Main scraping logic.

        Uses a two-tab approach: search results in main tab, case details in new tab.
        This preserves pagination state while processing cases.

        Args:
            page: Playwright page object

        Returns:
            dict: {'cases_processed': int, 'cases_found': int}
        """
        logger.info(f"Navigating to {PORTAL_URL}")
        page.goto(PORTAL_URL, wait_until='networkidle')

        # Step 1: Fill search form
        logger.info("Filling search form...")
        self._fill_search_form(page)

        # Step 2: Solve CAPTCHA and submit (handled together in solve_and_submit_captcha)
        logger.info("Solving CAPTCHA...")
        captcha_result = self._solve_captcha(page)
        # Note: _solve_captcha already clicks submit and waits for results

        # Step 3: Handle "no results" case - not an error, just no cases for this search
        if captcha_result == "no_results":
            logger.info("No cases match the search criteria - this is not an error")
            return {
                'cases_processed': 0,
                'cases_found': 0,
                'pages_processed': 0,
                'no_results': True
            }

        # Step 4: Check for truncated results (portal hit a limit)
        if self._check_for_truncated_results(page):
            raise TruncatedResultsError(
                "Results were truncated - need to narrow date range "
                "(quarterly -> bi-monthly -> monthly)"
            )

        # Step 5: Extract total count for validation
        # Per startup doc: "Use this to validate that you scraped all of the cases for each search"
        total_count = extract_total_count(page.content())
        cases_found = total_count if total_count else 0
        if total_count:
            logger.info(f"Found {total_count} total cases to review")

        # Step 6: Process all pages
        cases_processed = 0  # Foreclosure cases saved to database
        cases_reviewed = 0   # All cases reviewed (for validation)
        page_num = 1

        while True:
            logger.info(f"Processing page {page_num}...")

            # Extract cases from current page
            page_html = page.content()
            logger.debug(f"Search results HTML length: {len(page_html)}")

            # Debug: Check if caseLink elements exist
            if 'caseLink' in page_html:
                logger.debug("Found 'caseLink' in HTML")
            if 'data-url' in page_html:
                logger.debug("Found 'data-url' in HTML")
            else:
                logger.warning("'data-url' NOT found in HTML - case URLs may be missing")

            results = parse_search_results(page_html)
            cases = results['cases']

            # Debug: Log first case URL
            if cases:
                logger.debug(f"First case: {cases[0]['case_number']}, URL: {cases[0].get('case_url')}")

            for case_info in cases:
                cases_reviewed += 1  # Count every case we look at

                if self.limit and cases_processed >= self.limit:
                    logger.info(f"Reached limit of {self.limit} cases")
                    return {
                        'cases_processed': cases_processed,
                        'cases_found': cases_found,
                        'cases_reviewed': cases_reviewed,
                        'validation_passed': False,  # Limit was hit, incomplete
                        'validation_message': f"Stopped early due to limit ({self.limit})"
                    }

                # Process individual case (opens in new tab, then closes it)
                # This preserves search results page state for pagination
                if self._process_case_in_new_tab(page, case_info):
                    cases_processed += 1

            # Check for next page
            if not self._go_to_next_page(page):
                break

            page_num += 1

        # Validation: Ensure we reviewed all cases from search results
        validation_passed = True
        validation_message = "OK"

        if cases_found and cases_reviewed != cases_found:
            validation_passed = False
            validation_message = f"MISMATCH: Expected {cases_found} cases, reviewed {cases_reviewed}"
            logger.error(f"VALIDATION FAILED: {validation_message}")
        else:
            logger.info(f"VALIDATION PASSED: Reviewed {cases_reviewed}/{cases_found} cases")

        return {
            'cases_processed': cases_processed,
            'cases_found': cases_found,
            'cases_reviewed': cases_reviewed,
            'validation_passed': validation_passed,
            'validation_message': validation_message
        }

    def _fill_search_form(self, page):
        """Fill out the search form."""
        # Click advanced filter first
        click_advanced_filter(page)

        # Generate search text
        year = self.start_date.year
        search_text = get_search_text(self.county, year)

        # Fill the form
        fill_portal_form(
            page,
            county_name=f"{self.county.title()} County",
            start_date=self.start_date,
            end_date=self.end_date,
            search_text=search_text
        )

    def _solve_captcha(self, page):
        """
        Solve reCAPTCHA on the page.

        Returns:
            str: "no_results" if search returned no cases, None otherwise
        """
        result = solve_and_submit_captcha(page)
        if result == "no_results":
            return "no_results"
        if not result:
            raise Exception("Failed to solve CAPTCHA and submit form")
        return None

    def _check_for_truncated_results(self, page):
        """
        Check if results were truncated (portal hit a limit).

        The portal shows a red warning like:
        "The search returned XXX cases, but could have returned more.
         Please narrow the search by entering more precise criteria."

        This means we need to narrow the date range (quarterly -> bi-monthly -> monthly).

        Returns:
            bool: True if results were truncated
        """
        has_error, error_msg = check_for_error(page)
        if has_error and error_msg:
            # Check for truncation warning
            if 'could have returned more' in error_msg.lower():
                logger.warning(f"Results truncated: {error_msg}")
                return True
            # Also check legacy "too many" message
            if 'too many' in error_msg.lower():
                logger.warning(f"Too many results: {error_msg}")
                return True
        return False

    def _go_to_next_page(self, page):
        """Navigate to next page of results."""
        return navigate_next_page(page)

    def _process_case_in_new_tab(self, search_page, case_info):
        """
        Process a case in a new browser tab to preserve search results page state.

        Args:
            search_page: Playwright page object (search results - stays open)
            case_info: Dict with case_number and case_url

        Returns:
            bool: True if case was processed and saved
        """
        case_number = case_info['case_number']
        case_url = case_info.get('case_url')

        logger.info(f"Processing case: {case_number}")
        logger.debug(f"  Case URL: {case_url}")

        if not case_url or case_url == '#':
            logger.warning(f"  No valid URL for case {case_number}, skipping")
            return False

        # Open case detail in a new tab
        context = search_page.context
        detail_page = context.new_page()

        try:
            # Navigate to case detail
            detail_page.goto(case_url, wait_until='networkidle')

            # Wait for Angular ROA table to load (contains Case Type)
            try:
                detail_page.wait_for_selector('table.roa-caseinfo-info-rows', state='visible', timeout=30000)
                logger.debug(f"  ROA table found, Angular loaded")
            except Exception as e:
                logger.warning(f"  ROA table not found after 30s: {e}")
                # Try alternative wait
                import time
                time.sleep(3)

            # Parse case detail
            html_content = detail_page.content()
            logger.debug(f"  Page title: {detail_page.title()}")
            logger.debug(f"  HTML length: {len(html_content)}")

            case_data = parse_case_detail(html_content)

            # Check if foreclosure
            if not is_foreclosure_case(case_data):
                logger.info(f"  Not a foreclosure, skipping")
                return False

            logger.info(f"  ✓ Foreclosure case identified")

            # Save to database
            case_id = self._save_case(case_number, case_url, case_data)

            # Download documents (if any)
            if case_id:
                try:
                    doc_count = download_case_documents(
                        page=detail_page,
                        case_id=case_id,
                        county=self.county,
                        case_number=case_number
                    )
                    if doc_count > 0:
                        logger.info(f"  ✓ Downloaded {doc_count} document(s)")
                except Exception as e:
                    logger.warning(f"  Document download failed: {e}")

            return True

        finally:
            # Always close the detail tab to return to search results
            detail_page.close()

    def _process_case(self, page, case_info):
        """
        Process a single case.

        Args:
            page: Playwright page object
            case_info: Dict with case_number and case_url

        Returns:
            bool: True if case was processed and saved
        """
        case_number = case_info['case_number']
        case_url = case_info.get('case_url')

        logger.info(f"Processing case: {case_number}")
        logger.debug(f"  Case URL: {case_url}")

        if not case_url or case_url == '#':
            logger.warning(f"  No valid URL for case {case_number}, skipping")
            return False

        # Navigate to case detail
        page.goto(case_url, wait_until='networkidle')

        # Wait for Angular ROA table to load (contains Case Type)
        try:
            page.wait_for_selector('table.roa-caseinfo-info-rows', state='visible', timeout=30000)
            logger.debug(f"  ROA table found, Angular loaded")
        except Exception as e:
            logger.warning(f"  ROA table not found after 30s: {e}")
            # Try alternative wait
            import time
            time.sleep(3)

        # Parse case detail
        html_content = page.content()
        logger.debug(f"  Page title: {page.title()}")
        logger.debug(f"  HTML length: {len(html_content)}")

        case_data = parse_case_detail(html_content)

        # Check if foreclosure
        if not is_foreclosure_case(case_data):
            logger.info(f"  Not a foreclosure, skipping")
            return False

        logger.info(f"  ✓ Foreclosure case identified")

        # Save to database
        case_id = self._save_case(case_number, case_url, case_data)

        # Download documents (if any)
        if case_id:
            try:
                doc_count = download_case_documents(
                    page=page,
                    case_id=case_id,
                    county=self.county,
                    case_number=case_number
                )
                if doc_count > 0:
                    logger.info(f"  ✓ Downloaded {doc_count} document(s)")
            except Exception as e:
                logger.warning(f"  Document download failed: {e}")
                # Don't fail the case processing if document download fails

        return True

    def _save_case(self, case_number, case_url, case_data):
        """Save case and all related data to database.

        Uses upsert logic: if case already exists, update it and skip adding
        duplicate parties/events. If case is new, insert everything.

        Returns:
            tuple: (case_id, is_new) - the case ID and whether it was newly created
        """
        with get_session() as session:
            # Parse file_date string to date object
            file_date = None
            if case_data.get('file_date'):
                try:
                    file_date = datetime.strptime(case_data['file_date'], '%m/%d/%Y').date()
                except ValueError:
                    logger.warning(f"  Could not parse file_date: {case_data.get('file_date')}")

            # Check if case already exists
            existing_case = session.query(Case).filter_by(case_number=case_number).first()

            if existing_case:
                # Update existing case
                existing_case.case_type = case_data.get('case_type') or existing_case.case_type
                existing_case.case_status = case_data.get('case_status') or existing_case.case_status
                existing_case.case_url = case_url or existing_case.case_url
                existing_case.style = case_data.get('style') or existing_case.style
                existing_case.last_scraped_at = datetime.now()
                case = existing_case
                is_new = False
                logger.info(f"    ↻ Updated existing case (ID: {case.id})")
            else:
                # Create new case
                case = Case(
                    case_number=case_number,
                    county_code=self.county_code,
                    county_name=self.county.title(),
                    case_type=case_data.get('case_type'),
                    case_status=case_data.get('case_status'),
                    file_date=file_date,
                    case_url=case_url,
                    style=case_data.get('style'),
                    property_address=case_data.get('property_address'),
                    last_scraped_at=datetime.now()
                )
                session.add(case)
                session.flush()
                is_new = True

            # Only add parties/events/hearings for NEW cases (avoid duplicates)
            if is_new:
                # Add parties
                for party_data in case_data.get('parties', []):
                    party = Party(
                        case_id=case.id,
                        party_type=party_data.get('party_type'),
                        party_name=party_data.get('party_name')
                    )
                    session.add(party)

                # Add events
                for event_data in case_data.get('events', []):
                    # Parse event_date
                    event_date = None
                    if event_data.get('event_date'):
                        try:
                            event_date = datetime.strptime(event_data['event_date'], '%m/%d/%Y').date()
                        except ValueError:
                            pass

                    # Parse hearing_date if present
                    hearing_date = None
                    if event_data.get('hearing_date'):
                        try:
                            hearing_date = datetime.strptime(event_data['hearing_date'], '%m/%d/%Y %H:%M')
                        except ValueError:
                            pass

                    event = CaseEvent(
                        case_id=case.id,
                        event_date=event_date,
                        event_type=event_data.get('event_type'),
                        event_description=event_data.get('event_description'),
                        filed_by=event_data.get('filed_by'),
                        filed_against=event_data.get('filed_against'),
                        hearing_date=hearing_date,
                        document_url=event_data.get('document_url')
                    )
                    session.add(event)

                # Add hearings
                for hearing_data in case_data.get('hearings', []):
                    # Parse hearing_date
                    hearing_date = None
                    if hearing_data.get('hearing_date'):
                        try:
                            hearing_date = datetime.strptime(hearing_data['hearing_date'], '%m/%d/%Y').date()
                        except ValueError:
                            pass

                    hearing = Hearing(
                        case_id=case.id,
                        hearing_date=hearing_date,
                        hearing_time=hearing_data.get('hearing_time'),
                        hearing_type=hearing_data.get('hearing_type')
                    )
                    session.add(hearing)

            session.commit()

            # Log summary
            party_count = len(case_data.get('parties', []))
            event_count = len(case_data.get('events', []))
            hearing_count = len(case_data.get('hearings', []))
            if is_new:
                logger.info(f"  Saved to database (ID: {case.id}) - "
                           f"{party_count} parties, {event_count} events, {hearing_count} hearings")
            else:
                logger.debug(f"  Case already in database (ID: {case.id}), updated metadata")

            return case.id


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(description='NC Foreclosures Initial Scraper')

    parser.add_argument('--county', required=True, choices=['wake', 'durham', 'orange', 'chatham', 'lee', 'harnett'],
                        help='County to scrape')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--test', action='store_true', help='Test mode (limited scraping)')
    parser.add_argument('--limit', type=int, help='Limit number of cases to process')

    args = parser.parse_args()

    try:
        scraper = InitialScraper(
            county=args.county,
            start_date=args.start,
            end_date=args.end,
            test_mode=args.test,
            limit=args.limit
        )

        scrape_log_id = scraper.run()

        # Fetch final scrape log status
        from database.connection import get_session
        with get_session() as session:
            scrape_log = session.query(ScrapeLog).filter_by(id=scrape_log_id).first()

            logger.info("=" * 60)
            logger.info("SCRAPE SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Status: {scrape_log.status}")
            logger.info(f"Cases found: {scrape_log.cases_found}")
            logger.info(f"Cases processed: {scrape_log.cases_processed}")
            logger.info("=" * 60)

            exit_code = 0 if scrape_log.status == 'success' else 1

        sys.exit(exit_code)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
