#!/usr/bin/env python3
"""
Test to verify we're capturing actual event data, not just counts.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from scraper.page_parser import parse_case_detail
import json

def get_sample_case_url():
    from database.connection import get_session
    from database.models import SkippedCase

    with get_session() as session:
        # Get a case that likely has events
        case = session.query(SkippedCase).filter(
            SkippedCase.case_url.isnot(None)
        ).first()
        return case.case_url if case else None

def main():
    url = get_sample_case_url()
    print(f"URL: {url}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        page.goto(url, wait_until='networkidle', timeout=60000)
        page.wait_for_timeout(3000)

        html = page.content()
        case_data = parse_case_detail(html)

        print(f"Case Type: {case_data.get('case_type')}")
        print(f"Style: {case_data.get('style')}")
        print(f"\n{'='*60}")
        print(f"EVENTS ({len(case_data.get('events', []))} total):")
        print(f"{'='*60}")

        for i, event in enumerate(case_data.get('events', [])[:10]):  # Show first 10
            print(f"\nEvent {i+1}:")
            print(f"  event_date: {event.get('event_date')}")
            print(f"  event_type: {event.get('event_type')}")
            print(f"  event_description: {event.get('event_description', '')[:100]}...")
            print(f"  filed_by: {event.get('filed_by')}")

        if len(case_data.get('events', [])) > 10:
            print(f"\n... and {len(case_data.get('events', [])) - 10} more events")

        browser.close()

if __name__ == '__main__':
    main()
