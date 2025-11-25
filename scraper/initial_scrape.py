"""Initial scrape to populate database with historical foreclosure data."""

import argparse
import sys
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from database.connection import get_session
from database.models import Case, CaseEvent, ScrapeLog
from scraper.vpn_manager import verify_vpn_or_exit
from scraper.captcha_solver import solve_recaptcha
from scraper.page_parser import is_foreclosure_case, parse_search_results, parse_case_detail, extract_total_count
from common.county_codes import get_county_code, get_search_text, is_valid_county
from common.logger import setup_logger

logger = setup_logger(__name__)

# NC Courts Portal URL
PORTAL_URL = 'https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29'


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

        # Step 1: Verify VPN
        verify_vpn_or_exit()

        # Step 2: Create scrape log
        scrape_log = self._create_scrape_log()

        try:
            # Step 3: Launch browser and scrape
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)  # headless=False for development
                page = browser.new_page()

                try:
                    cases_processed = self._scrape_cases(page, scrape_log)
                    scrape_log.cases_processed = cases_processed
                    scrape_log.status = 'success'
                    logger.info(f"✓ Scrape completed successfully: {cases_processed} cases processed")

                except Exception as e:
                    logger.error(f"Scrape failed: {e}", exc_info=True)
                    scrape_log.status = 'failed'
                    scrape_log.error_message = str(e)
                    raise

                finally:
                    browser.close()

        finally:
            # Update scrape log
            self._complete_scrape_log(scrape_log)

        return scrape_log

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
            log_id = scrape_log.id

        logger.info(f"Created scrape log (ID: {log_id})")
        return scrape_log

    def _complete_scrape_log(self, scrape_log):
        """Update scrape log with final status."""
        with get_session() as session:
            log = session.query(ScrapeLog).filter_by(id=scrape_log.id).first()
            if log:
                log.completed_at = datetime.now()
                log.status = scrape_log.status
                log.cases_processed = scrape_log.cases_processed
                log.cases_found = scrape_log.cases_found
                log.error_message = scrape_log.error_message
                session.commit()

    def _scrape_cases(self, page, scrape_log):
        """
        Main scraping logic.

        Args:
            page: Playwright page object
            scrape_log: ScrapeLog object to update

        Returns:
            int: Number of cases processed
        """
        logger.info(f"Navigating to {PORTAL_URL}")
        page.goto(PORTAL_URL, wait_until='networkidle')

        # Step 1: Fill search form
        logger.info("Filling search form...")
        self._fill_search_form(page)

        # Step 2: Solve CAPTCHA
        logger.info("Solving CAPTCHA...")
        self._solve_captcha(page)

        # Step 3: Submit search
        logger.info("Submitting search...")
        page.click('button[type="submit"]')  # Placeholder selector
        page.wait_for_load_state('networkidle')

        # Step 4: Check for errors
        if self._check_for_too_many_results(page):
            logger.error("Too many results error - need to reduce date range")
            raise Exception("Too many results - implement date range splitting")

        # Step 5: Extract total count
        total_count = extract_total_count(page.content())
        if total_count:
            logger.info(f"Found {total_count} total cases")
            scrape_log.cases_found = total_count

        # Step 6: Process all pages
        cases_processed = 0
        page_num = 1

        while True:
            logger.info(f"Processing page {page_num}...")

            # Extract cases from current page
            results = parse_search_results(page.content())
            cases = results['cases']

            for case_info in cases:
                if self.limit and cases_processed >= self.limit:
                    logger.info(f"Reached limit of {self.limit} cases")
                    return cases_processed

                # Process individual case
                if self._process_case(page, case_info):
                    cases_processed += 1

            # Check for next page
            if not self._go_to_next_page(page):
                break

            page_num += 1

        return cases_processed

    def _fill_search_form(self, page):
        """Fill out the search form."""
        # TODO: Implement based on actual portal structure
        # For now, this is a placeholder

        year = self.start_date.year
        search_text = get_search_text(self.county, year)

        logger.info(f"Search text: {search_text}")
        logger.info(f"County: {self.county.title()}")
        logger.info(f"Dates: {self.start_date} to {self.end_date}")

        # Placeholder - actual implementation needs portal exploration
        logger.warning("Search form filling not yet implemented - needs portal structure")

    def _solve_captcha(self, page):
        """Solve reCAPTCHA on the page."""
        # TODO: Implement based on actual portal structure
        # For now, this is a placeholder

        logger.warning("CAPTCHA solving not yet implemented - needs portal structure")

        # Example:
        # site_key = page.locator('div.g-recaptcha').get_attribute('data-sitekey')
        # token = solve_recaptcha(PORTAL_URL, site_key)
        # page.evaluate(f"document.getElementById('g-recaptcha-response').value = '{token}'")

    def _check_for_too_many_results(self, page):
        """Check if 'too many results' error is displayed."""
        # TODO: Implement based on actual portal structure
        return False

    def _go_to_next_page(self, page):
        """Navigate to next page of results."""
        # TODO: Implement based on actual portal structure
        return False

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
        case_url = case_info['case_url']

        logger.info(f"Processing case: {case_number}")

        # Navigate to case detail
        page.goto(case_url, wait_until='networkidle')

        # Parse case detail
        case_data = parse_case_detail(page.content())

        # Check if foreclosure
        if not is_foreclosure_case(case_data):
            logger.info(f"  Not a foreclosure, skipping")
            return False

        logger.info(f"  ✓ Foreclosure case identified")

        # Save to database
        self._save_case(case_number, case_url, case_data)

        return True

    def _save_case(self, case_number, case_url, case_data):
        """Save case to database."""
        with get_session() as session:
            # Create case
            case = Case(
                case_number=case_number,
                county_code=self.county_code,
                county_name=self.county.title(),
                case_type=case_data.get('case_type'),
                case_status=case_data.get('case_status'),
                file_date=case_data.get('file_date'),
                case_url=case_url,
                property_address=case_data.get('property_address'),
                last_scraped_at=datetime.now()
            )
            session.add(case)
            session.flush()

            # Add events
            for event_data in case_data.get('events', []):
                event = CaseEvent(
                    case_id=case.id,
                    event_date=event_data.get('event_date'),
                    event_type=event_data.get('event_type'),
                    event_description=event_data.get('event_description')
                )
                session.add(event)

            session.commit()
            logger.info(f"  Saved to database (ID: {case.id})")


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

        scrape_log = scraper.run()

        logger.info("=" * 60)
        logger.info("SCRAPE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Status: {scrape_log.status}")
        logger.info(f"Cases found: {scrape_log.cases_found}")
        logger.info(f"Cases processed: {scrape_log.cases_processed}")
        logger.info("=" * 60)

        sys.exit(0 if scrape_log.status == 'success' else 1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
