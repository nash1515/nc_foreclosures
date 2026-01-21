#!/usr/bin/env python3
"""
Quick test of xvfb + headed mode
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from scraper.page_parser import parse_case_detail

def get_sample_case_url():
    from database.connection import get_session
    from database.models import SkippedCase

    with get_session() as session:
        case = session.query(SkippedCase).filter(
            SkippedCase.case_url.isnot(None)
        ).first()
        return case.case_url if case else None

def main():
    url = get_sample_case_url()
    print(f"URL: {url}")
    print(f"DISPLAY: {os.environ.get('DISPLAY', 'not set')}")

    with sync_playwright() as p:
        # Use headed mode - xvfb will provide the virtual display
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        print("Navigating...")
        page.goto(url, wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)

        html = page.content()
        print(f"HTML length: {len(html):,}")

        case_data = parse_case_detail(html)
        print(f"Case Type: {case_data.get('case_type')}")
        print(f"Events: {len(case_data.get('events', []))}")
        print(f"Parties: {len(case_data.get('parties', []))}")

        if case_data.get('events'):
            print("SUCCESS - xvfb + headed mode works!")
        else:
            print("FAILURE - no events parsed")

        browser.close()

if __name__ == '__main__':
    main()
