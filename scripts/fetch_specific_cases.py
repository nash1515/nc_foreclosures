#!/usr/bin/env python3
"""Fetch specific cases by case number.

This script searches for specific case numbers and adds them to the database
if they are foreclosures. Use this to fill gaps in the database.

Usage:
    PYTHONPATH=$(pwd) venv/bin/python scripts/fetch_specific_cases.py 25SP002519-910 24SP000376-910
"""

import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Add project root to path
sys.path.insert(0, '.')

from database.connection import get_session
from database.models import Case, CaseEvent, Party, Hearing, SkippedCase
from scraper.captcha_solver import solve_recaptcha
from scraper.page_parser import is_foreclosure_case, parse_case_detail
from scraper.portal_selectors import PORTAL_URL, RECAPTCHA_SITE_KEY
from scraper.pdf_downloader import download_case_documents
from common.county_codes import get_county_code, get_county_name
from common.logger import setup_logger

logger = setup_logger(__name__)


def fetch_cases(case_numbers: list):
    """Fetch specific cases by case number."""

    results = {
        'found': [],
        'saved': [],
        'skipped': [],
        'not_found': [],
        'errors': []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        for case_number in case_numbers:
            logger.info(f"Searching for {case_number}...")

            try:
                # Navigate to portal
                page.goto(PORTAL_URL, wait_until='networkidle')
                time.sleep(2)

                # Fill in case number directly (include county code)
                page.fill('#caseCriteria_SearchCriteria', case_number)
                logger.info(f"  Filled search: {case_number}")

                # Solve CAPTCHA
                logger.info("  Solving CAPTCHA...")
                token = solve_recaptcha(PORTAL_URL, RECAPTCHA_SITE_KEY)
                page.evaluate(f'''
                    document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                    document.getElementById('g-recaptcha-response').value = '{token}';
                ''')
                logger.info("  CAPTCHA token injected")

                # Submit search - use correct selector
                page.click('#btnSSSubmit')
                logger.info("  Submit button clicked, waiting for results...")

                # Wait for search results page to load
                # The portal redirects to WorkspaceMode?p=0 after search
                max_wait = 60
                poll_interval = 2
                waited = 0
                results_loaded = False

                while waited < max_wait:
                    current_url = page.url
                    page_text = page.content()

                    # Check for "no cases" message
                    if "No cases match your search" in page_text or "No items to display" in page_text:
                        logger.info("  ✓ No results found")
                        results_loaded = True
                        break

                    # Check if we're on results page and have a table with case data
                    if 'WorkspaceMode' in current_url or 'SearchResults' in current_url:
                        # Look for the case number in the results
                        if case_number in page_text:
                            logger.info("  ✓ Results page loaded with case")
                            results_loaded = True
                            break

                    time.sleep(poll_interval)
                    waited += poll_interval

                if not results_loaded:
                    raise Exception(f"Results did not load after {max_wait} seconds")

                time.sleep(2)

                # Check if case was found in results
                page_text = page.content()
                if case_number not in page_text:
                    logger.warning(f"  Case {case_number} not found in portal")
                    results['not_found'].append(case_number)
                    continue

                # Find and click the case link - it's a regular link with the case number text
                # The portal uses table rows with links that open in new tabs
                case_link = page.locator(f'a:has-text("{case_number}")').first

                if case_link.count() == 0:
                    # Try without suffix
                    base_number = case_number.split('-')[0]
                    case_link = page.locator(f'a:has-text("{base_number}")').first

                if case_link.count() == 0:
                    logger.warning(f"  Case {case_number} link not found in search results")
                    results['not_found'].append(case_number)
                    continue

                logger.info(f"  Found case link, clicking to open details...")
                results['found'].append(case_number)

                # Click the case link - it opens in a new tab
                # Listen for new page/tab before clicking
                with context.expect_page() as new_page_info:
                    case_link.click()

                detail_page = new_page_info.value
                detail_page.wait_for_load_state('networkidle')
                time.sleep(3)  # Give Angular app time to render

                # Get the case URL from the new tab
                case_url = detail_page.url
                logger.info(f"  Case detail page opened: {case_url[:80]}...")

                # Parse case detail
                content = detail_page.content()
                case_data = parse_case_detail(content)

                # Extract county from case number
                county_code = case_number.split('-')[-1] if '-' in case_number else None
                county_name = get_county_name(county_code) if county_code else None

                # Check if it's a foreclosure
                if is_foreclosure_case(case_data):
                    logger.info(f"  ✓ {case_number} is a foreclosure case")

                    # Save to database
                    case_id = save_case(case_number, case_url, county_code, county_name, case_data)
                    if case_id:
                        results['saved'].append(case_number)

                        # Download documents
                        try:
                            download_case_documents(case_id, case_data.get('events', []), detail_page)
                        except Exception as e:
                            logger.warning(f"  Document download error: {e}")
                    else:
                        logger.info(f"  Case already exists in database")
                else:
                    logger.info(f"  ✗ {case_number} is not a foreclosure")
                    results['skipped'].append(case_number)

                detail_page.close()

            except Exception as e:
                logger.error(f"  Error fetching {case_number}: {e}")
                results['errors'].append((case_number, str(e)))

        browser.close()

    return results


def save_case(case_number, case_url, county_code, county_name, case_data):
    """Save case to database if it doesn't exist."""

    with get_session() as session:
        # Check if case exists
        existing = session.query(Case).filter_by(case_number=case_number).first()
        if existing:
            return None

        # Parse file date
        file_date = None
        if case_data.get('file_date'):
            try:
                file_date = datetime.strptime(case_data['file_date'], '%m/%d/%Y').date()
            except:
                pass

        # Create case
        case = Case(
            case_number=case_number,
            county_code=county_code,
            county_name=county_name,
            case_type=case_data.get('case_type'),
            case_status=case_data.get('case_status'),
            file_date=file_date,
            style=case_data.get('style'),
            case_url=case_url,
            classification='upcoming'
        )
        session.add(case)
        session.flush()

        # Add events
        for event_data in case_data.get('events', []):
            event_date = None
            if event_data.get('event_date'):
                try:
                    event_date = datetime.strptime(event_data['event_date'], '%m/%d/%Y').date()
                except:
                    pass

            event = CaseEvent(
                case_id=case.id,
                event_date=event_date,
                event_type=event_data.get('event_type'),
                filed_by=event_data.get('filed_by'),
                filed_against=event_data.get('filed_against'),
                document_url=event_data.get('document_url')
            )
            session.add(event)

        # Add parties
        for party_data in case_data.get('parties', []):
            party = Party(
                case_id=case.id,
                party_type=party_data.get('party_type'),
                party_name=party_data.get('party_name')
            )
            session.add(party)

        # Add hearings
        for hearing_data in case_data.get('hearings', []):
            hearing_date = None
            if hearing_data.get('hearing_date'):
                try:
                    hearing_date = datetime.strptime(hearing_data['hearing_date'], '%m/%d/%Y').date()
                except:
                    pass

            hearing = Hearing(
                case_id=case.id,
                hearing_date=hearing_date,
                hearing_time=hearing_data.get('hearing_time'),
                hearing_type=hearing_data.get('hearing_type')
            )
            session.add(hearing)

        session.commit()
        logger.info(f"  Saved case {case_number} with ID {case.id}")
        return case.id


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/fetch_specific_cases.py CASE1 CASE2 ...")
        print("Example: python scripts/fetch_specific_cases.py 25SP002519-910 24SP000376-910")
        sys.exit(1)

    case_numbers = sys.argv[1:]
    logger.info(f"Fetching {len(case_numbers)} cases: {case_numbers}")

    results = fetch_cases(case_numbers)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Found: {len(results['found'])}")
    print(f"Saved: {len(results['saved'])}")
    print(f"Skipped (not foreclosure): {len(results['skipped'])}")
    print(f"Not found: {len(results['not_found'])}")
    print(f"Errors: {len(results['errors'])}")

    if results['saved']:
        print(f"\nSaved cases: {', '.join(results['saved'])}")
    if results['not_found']:
        print(f"\nNot found: {', '.join(results['not_found'])}")
    if results['errors']:
        print(f"\nErrors:")
        for case_num, error in results['errors']:
            print(f"  {case_num}: {error}")


if __name__ == '__main__':
    main()
