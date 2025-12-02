"""Date range scraper - searches all counties in a single search.

This is more efficient for short date ranges (catch-up or daily scrapes)
because it only requires ONE CAPTCHA solve instead of 6.

Usage:
    from scraper.date_range_scrape import DateRangeScraper
    scraper = DateRangeScraper(start_date='2025-11-27', end_date='2025-11-30')
    results = scraper.run()
"""

import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

from database.connection import get_session
from database.models import Case, CaseEvent, Party, Hearing, ScrapeLog
from scraper.captcha_solver import solve_recaptcha
from scraper.page_parser import is_foreclosure_case, parse_search_results, parse_case_detail, extract_total_count
from scraper.portal_interactions import (
    click_advanced_filter,
    fill_search_form,
    solve_and_submit_captcha,
    check_for_error,
    extract_total_count_from_page,
    go_to_next_page
)
from scraper.portal_selectors import PORTAL_URL
from scraper.pdf_downloader import download_case_documents
from common.county_codes import get_county_code, get_county_name, COUNTY_CODES
from common.config import config
from common.logger import setup_logger

logger = setup_logger(__name__)

# Our target counties
TARGET_COUNTIES = ['wake', 'durham', 'orange', 'chatham', 'lee', 'harnett']


class DateRangeScraper:
    """Scraper for multi-county date range searches."""

    def __init__(self, start_date, end_date, counties=None, test_mode=False, limit=None):
        """
        Initialize scraper.

        Args:
            start_date: Start date (YYYY-MM-DD string)
            end_date: End date (YYYY-MM-DD string)
            counties: List of county names (default: all 6 target counties)
            test_mode: If True, limit scraping for testing
            limit: Maximum number of cases to process (for testing)
        """
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        self.end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        self.counties = counties or TARGET_COUNTIES
        self.test_mode = test_mode
        self.limit = limit
        self.scrape_log_id = None

        # Validate counties
        for county in self.counties:
            if county.lower() not in COUNTY_CODES:
                raise ValueError(f"Invalid county: {county}")

        logger.info(f"DateRangeScraper initialized")
        logger.info(f"  Date range: {self.start_date} to {self.end_date}")
        logger.info(f"  Counties: {', '.join(self.counties)}")
        if test_mode:
            logger.info(f"  TEST MODE - Limit: {limit} cases")

    def run(self):
        """Execute the scraping process."""
        logger.info("=" * 60)
        logger.info("STARTING DATE RANGE SCRAPE")
        logger.info("=" * 60)

        # Create scrape log
        self.scrape_log_id = self._create_scrape_log()
        cases_processed = 0
        status = 'failed'
        error_message = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                # Use a real Chrome user-agent to avoid bot detection
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()

                try:
                    result = self._scrape_cases(page, context)
                    cases_processed = result.get('cases_processed', 0)
                    status = 'success'

                except Exception as e:
                    error_message = str(e)
                    logger.error(f"Scrape failed: {e}")
                    raise

                finally:
                    context.close()
                    browser.close()

        finally:
            self._update_scrape_log(status, cases_processed, error_message)

        logger.info("=" * 60)
        logger.info(f"SCRAPE COMPLETE: {cases_processed} foreclosures saved")
        logger.info("=" * 60)

        return {
            'cases_processed': cases_processed,
            'status': status,
            'error': error_message
        }

    def _create_scrape_log(self):
        """Create a scrape log entry."""
        with get_session() as session:
            log = ScrapeLog(
                scrape_type='daily',
                county_code='MULTI',  # Special code for multi-county searches
                start_date=self.start_date,
                end_date=self.end_date,
                status='in_progress'
            )
            session.add(log)
            session.commit()
            return log.id

    def _update_scrape_log(self, status, cases_processed, error_message=None):
        """Update the scrape log with results."""
        with get_session() as session:
            log = session.query(ScrapeLog).filter_by(id=self.scrape_log_id).first()
            if log:
                log.status = status
                log.cases_processed = cases_processed
                log.error_message = error_message
                log.completed_at = datetime.utcnow()
                session.commit()

    def _scrape_cases(self, page, context):
        """Main scraping logic."""
        logger.info(f"Navigating to {PORTAL_URL}")
        page.goto(PORTAL_URL, wait_until='networkidle')

        # Fill search form with ALL counties selected
        click_advanced_filter(page)

        # Generate search text (year-based)
        year = self.start_date.year
        search_text = f"{str(year)[-2:]}SP*"

        # Get county names for the form (e.g., "Wake County")
        county_names = [f"{c.title()} County" for c in self.counties]

        fill_search_form(
            page,
            county_names=county_names,
            start_date=self.start_date,
            end_date=self.end_date,
            search_text=search_text
        )

        # Solve CAPTCHA and submit
        logger.info("Solving CAPTCHA...")
        captcha_result = solve_and_submit_captcha(page)

        if captcha_result == "no_results":
            logger.info("No cases match the search criteria")
            return {'cases_processed': 0, 'cases_found': 0}

        if not captcha_result:
            raise Exception("Failed to solve CAPTCHA and submit form")

        # Check for truncated results
        has_error, error_msg = check_for_error(page)
        if has_error and error_msg:
            if 'could have returned more' in error_msg.lower() or 'too many' in error_msg.lower():
                raise Exception(f"Results truncated - date range too wide: {error_msg}")

        # Extract total count
        total_count = extract_total_count_from_page(page)
        logger.info(f"Found {total_count or 'unknown'} total cases")

        # Process all pages
        cases_processed = 0
        page_num = 1

        while True:
            logger.info(f"Processing page {page_num}...")

            page_html = page.content()
            results = parse_search_results(page_html)
            cases = results['cases']

            for case_info in cases:
                if self.limit and cases_processed >= self.limit:
                    logger.info(f"Reached limit of {self.limit} cases")
                    return {'cases_processed': cases_processed}

                # Process case in new tab
                if self._process_case_in_new_tab(context, case_info):
                    cases_processed += 1

            # Check for next page
            if not go_to_next_page(page):
                break

            page_num += 1

        return {
            'cases_processed': cases_processed,
            'cases_found': total_count or cases_processed
        }

    def _process_case_in_new_tab(self, context, case_info):
        """Process a case in a new browser tab."""
        case_number = case_info['case_number']
        case_url = case_info.get('case_url')
        location = case_info.get('location', '')

        logger.info(f"Processing case: {case_number} ({location})")

        if not case_url:
            logger.warning(f"  No URL for case {case_number}, skipping")
            return False

        # Determine county from case number suffix (e.g., 25SP001116-310 -> 310 = Durham)
        # The case number format is YYSPNNNNNN-CCC where CCC is the county code
        county_code = None
        county_name = None

        # Try to extract county code from case number suffix
        if '-' in case_number:
            suffix = case_number.split('-')[-1]
            county_name_from_code = get_county_name(suffix)
            if county_name_from_code:
                county_code = suffix
                county_name = county_name_from_code.lower()
                logger.debug(f"  Extracted county from case number: {county_name} ({county_code})")

        # Fallback: try to match county from location field (if available)
        if not county_code and location:
            for county in self.counties:
                if county.lower() in location.lower():
                    county_code = get_county_code(county)
                    county_name = county
                    break

        if not county_code:
            logger.warning(f"  Could not determine county from case number '{case_number}' or location '{location}', skipping")
            return False

        # Open case in new tab
        detail_page = context.new_page()

        try:
            detail_page.goto(case_url, wait_until='networkidle')

            # Wait for Angular app to load
            try:
                detail_page.wait_for_selector('table.roa-caseinfo-info-rows', state='visible', timeout=30000)
            except:
                logger.warning(f"  Case detail page didn't load properly for {case_number}")
                return False

            # Parse case details
            detail_html = detail_page.content()
            case_data = parse_case_detail(detail_html)

            # Check if this is a foreclosure case
            if not is_foreclosure_case(case_data):
                logger.debug(f"  {case_number} is not a foreclosure case, skipping")
                return False

            logger.info(f"  ✓ {case_number} is a foreclosure case")

            # Save to database
            saved = self._save_case(case_number, case_url, county_code, county_name, case_data)

            # Download PDFs if we saved the case
            if saved and not self.test_mode:
                try:
                    download_case_documents(detail_page, case_number, county_name)
                except Exception as e:
                    logger.warning(f"  Failed to download documents for {case_number}: {e}")

            return saved

        except Exception as e:
            logger.error(f"  Error processing case {case_number}: {e}")
            return False

        finally:
            detail_page.close()

    def _save_case(self, case_number, case_url, county_code, county_name, case_data):
        """Save case to database with upsert logic."""
        with get_session() as session:
            # Check if case already exists
            existing = session.query(Case).filter_by(case_number=case_number).first()

            if existing:
                # Update existing case
                existing.case_type = case_data.get('case_type')
                existing.case_status = case_data.get('case_status')
                existing.style = case_data.get('style')
                existing.updated_at = datetime.utcnow()
                logger.info(f"  Updated existing case {case_number}")
                session.commit()
                return True

            # Create new case
            case = Case(
                case_number=case_number,
                county_code=county_code,
                county_name=county_name.title(),
                case_type=case_data.get('case_type'),
                case_status=case_data.get('case_status'),
                file_date=case_data.get('file_date'),
                style=case_data.get('style'),
                case_url=case_url,
                scrape_log_id=self.scrape_log_id
            )
            session.add(case)
            session.flush()

            # Add parties
            for party_data in case_data.get('parties', []):
                party = Party(
                    case_id=case.id,
                    party_type=party_data.get('party_type'),
                    party_name=party_data.get('name')
                )
                session.add(party)

            # Add events
            for event_data in case_data.get('events', []):
                event = CaseEvent(
                    case_id=case.id,
                    event_date=event_data.get('date'),
                    event_type=event_data.get('event_type'),
                    filed_by=event_data.get('filed_by'),
                    filed_against=event_data.get('filed_against'),
                    hearing_date=event_data.get('hearing_date'),
                    document_url=event_data.get('document_url')
                )
                session.add(event)

            # Add hearings
            for hearing_data in case_data.get('hearings', []):
                hearing = Hearing(
                    case_id=case.id,
                    hearing_date=hearing_data.get('date'),
                    hearing_time=hearing_data.get('time'),
                    hearing_type=hearing_data.get('type')
                )
                session.add(hearing)

            session.commit()
            logger.info(f"  ✓ Saved new case {case_number}")
            return True


def run_date_range_scrape(start_date, end_date, counties=None, dry_run=False):
    """
    Run a date range scrape for all counties.

    Args:
        start_date: Start date (YYYY-MM-DD or date object)
        end_date: End date (YYYY-MM-DD or date object)
        counties: List of county names (default: all 6)
        dry_run: If True, just show what would be done

    Returns:
        dict: Results with cases_processed, status, error
    """
    # Convert date objects to strings if needed
    if hasattr(start_date, 'strftime'):
        start_date = start_date.strftime('%Y-%m-%d')
    if hasattr(end_date, 'strftime'):
        end_date = end_date.strftime('%Y-%m-%d')

    if dry_run:
        counties_list = counties or TARGET_COUNTIES
        logger.info("=" * 60)
        logger.info("[DRY RUN] DATE RANGE SCRAPE")
        logger.info("=" * 60)
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Counties: {', '.join(counties_list)}")
        logger.info("Would search all counties in a single search (1 CAPTCHA)")
        logger.info("=" * 60)
        return {
            'cases_processed': 0,
            'status': 'dry_run',
            'error': None
        }

    scraper = DateRangeScraper(
        start_date=start_date,
        end_date=end_date,
        counties=counties
    )
    return scraper.run()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Date range scraper for NC foreclosures')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--county', help='Specific county (optional, default: all)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--limit', type=int, help='Limit cases to process')

    args = parser.parse_args()

    counties = [args.county] if args.county else None

    if args.dry_run:
        result = run_date_range_scrape(args.start, args.end, counties, dry_run=True)
    else:
        scraper = DateRangeScraper(
            start_date=args.start,
            end_date=args.end,
            counties=counties,
            limit=args.limit
        )
        result = scraper.run()

    sys.exit(0 if result['status'] in ('success', 'dry_run') else 1)
