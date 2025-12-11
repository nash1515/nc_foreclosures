#!/usr/bin/env python3
"""
Download documents for cases that have 0 documents in the database.

Problem: 303 cases have 0 documents because:
1. Early scrapes didn't download documents properly
2. The date_range_scrape only downloads docs on first case creation, not on updates

This script:
1. Finds all cases with 0 documents
2. For each case, navigates to the case_url
3. Downloads all documents using the existing pdf_downloader functions
4. Tracks progress and reports results

Usage:
    PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/download_missing_documents.py [--yes]
"""
import sys
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

import argparse
import time
from playwright.sync_api import sync_playwright
from sqlalchemy import text
from database.connection import get_session
from database.models import Case, Document
from scraper.pdf_downloader import download_case_documents
from common.logger import setup_logger

logger = setup_logger('download_missing')


def get_cases_with_no_documents():
    """
    Query database for cases with 0 documents.

    Returns:
        list: List of tuples (case_id, case_number, case_url, county_name)
    """
    with get_session() as session:
        result = session.execute(text('''
            SELECT c.id, c.case_number, c.case_url, c.county_name
            FROM cases c
            LEFT JOIN documents d ON c.id = d.case_id
            GROUP BY c.id, c.case_number, c.case_url, c.county_name
            HAVING COUNT(d.id) = 0
            ORDER BY c.county_name, c.case_number
        ''')).fetchall()

        return [(r[0], r[1], r[2], r[3]) for r in result]


def main():
    """
    Main function to download missing documents.
    """
    parser = argparse.ArgumentParser(description='Download documents for cases with 0 documents')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    print("=" * 60)
    print("NC Foreclosures - Download Missing Documents")
    print("=" * 60)
    print()

    # Get cases with 0 documents
    logger.info("Querying database for cases with 0 documents...")
    case_data = get_cases_with_no_documents()

    if not case_data:
        print("No cases found with 0 documents. All cases have documents!")
        return

    print(f"Found {len(case_data)} cases with 0 documents\n")

    # Show county breakdown
    county_counts = {}
    for _, _, _, county in case_data:
        county_counts[county] = county_counts.get(county, 0) + 1

    print("Cases by county:")
    for county, count in sorted(county_counts.items()):
        print(f"  {county}: {count}")
    print()

    # Ask for confirmation unless --yes flag is used
    if not args.yes:
        response = input(f"Download documents for all {len(case_data)} cases? (y/n): ")
        if response.lower() not in ['y', 'yes']:
            print("Aborted.")
            return

    print()
    logger.info("Starting document download process...")

    # Launch browser
    with sync_playwright() as p:
        logger.info("Launching browser (headless=False for Angular support)...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        # Statistics
        downloaded = 0
        failed = 0
        no_docs = 0
        no_url = 0

        for i, (case_id, case_number, case_url, county_name) in enumerate(case_data):
            print(f"\n[{i+1}/{len(case_data)}] Processing {case_number} ({county_name})...")
            logger.info(f"Processing case {case_number} (ID: {case_id})")

            if not case_url:
                print(f"  ⚠️  No URL available, skipping")
                logger.warning(f"Case {case_number} has no URL")
                no_url += 1
                continue

            page = context.new_page()
            try:
                # Navigate to case page
                logger.debug(f"Navigating to {case_url}")
                page.goto(case_url, wait_until='networkidle', timeout=60000)

                # Wait for page to load (Angular needs time to render)
                page.wait_for_selector('table.roa-caseinfo-info-rows', state='visible', timeout=30000)

                # Small delay for Angular to render document buttons
                time.sleep(1.5)

                # Download documents
                county = county_name.lower() if county_name else 'unknown'
                count = download_case_documents(page, case_id, county, case_number)

                if count > 0:
                    print(f"  ✓ Downloaded {count} document(s)")
                    logger.info(f"Successfully downloaded {count} documents for {case_number}")
                    downloaded += 1
                else:
                    print(f"  ℹ️  No documents found on case page")
                    logger.info(f"No documents found for {case_number}")
                    no_docs += 1

            except Exception as e:
                print(f"  ✗ Error: {e}")
                logger.error(f"Failed to process {case_number}: {e}", exc_info=True)
                failed += 1

            finally:
                page.close()

            # Be polite to the server - wait between requests
            time.sleep(1)

        browser.close()

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total cases processed:        {len(case_data)}")
    print(f"Cases with downloads:         {downloaded}")
    print(f"Cases with no documents:      {no_docs}")
    print(f"Cases with no URL:            {no_url}")
    print(f"Cases that failed:            {failed}")
    print()

    # Verify results
    remaining = get_cases_with_no_documents()
    print(f"Cases still with 0 documents: {len(remaining)}")

    if len(remaining) > 0:
        print()
        print("Cases that still need documents:")
        for case_id, case_number, case_url, county in remaining[:10]:
            status = "no URL" if not case_url else "failed or no docs"
            print(f"  {case_number} ({county}) - {status}")
        if len(remaining) > 10:
            print(f"  ... and {len(remaining) - 10} more")

    logger.info("Document download process completed")


if __name__ == '__main__':
    main()
