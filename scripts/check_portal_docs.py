#!/usr/bin/env python3
"""Check documents for a case from the NC Courts Portal."""

import asyncio
import sys
from playwright.async_api import async_playwright
from database.connection import get_session
from database.models import Case
from scraper.page_parser import parse_case_detail


async def check_portal_documents(case_number: str):
    print(f"\n{'='*70}")
    print(f"Checking {case_number} from NC Courts Portal")
    print('='*70)

    with get_session() as session:
        case = session.query(Case).filter(Case.case_number == case_number).first()

        if not case or not case.case_url:
            print(f"Case not found or no URL")
            return

        case_url = case.case_url
        case_style = case.style

    print(f"Case URL: {case_url}")
    print(f"Respondent: {case_style}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto(case_url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(3)

        # Look for event rows and expand them to see documents
        # The portal uses expandable rows - click to expand
        event_rows = await page.query_selector_all('tr.ng-star-inserted')
        print(f"\nFound {len(event_rows)} event rows")

        # Look specifically for Report of Sale events
        for row in event_rows:
            text = await row.inner_text()
            if 'Report' in text and 'Sale' in text:
                print(f"\n=== Found Report of Sale row ===")
                print(f"Row text: {text[:200]}")

                # Try to find and click the expand button
                expand_btn = await row.query_selector('button, .expand-icon, mat-icon')
                if expand_btn:
                    print("Found expand button, clicking...")
                    await expand_btn.click()
                    await asyncio.sleep(1)

                    # Check for document links
                    doc_links = await page.query_selector_all('a[href*="document"], button:has-text("View")')
                    print(f"Found {len(doc_links)} document links after expand")

        await browser.close()


async def main():
    case_numbers = sys.argv[1:] if len(sys.argv) > 1 else ['25SP001024-910', '25SP001017-910']

    for case_num in case_numbers:
        await check_portal_documents(case_num)
        print("\n")


if __name__ == '__main__':
    asyncio.run(main())
