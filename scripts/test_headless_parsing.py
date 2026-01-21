#!/usr/bin/env python3
"""
Test script to compare headless vs headed mode for NC Courts portal parsing.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from scraper.page_parser import parse_case_detail

# Get a sample case URL from skipped_cases
def get_sample_case_url():
    from database.connection import get_session
    from database.models import SkippedCase

    with get_session() as session:
        case = session.query(SkippedCase).filter(
            SkippedCase.case_url.isnot(None)
        ).first()
        return case.case_url if case else None

def test_parsing(url: str, config: dict) -> dict:
    """Test parsing with given configuration."""
    name = config['name']
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    with sync_playwright() as p:
        # Build launch args
        launch_args = {
            'headless': config.get('headless', True),
        }

        # Add browser args if specified
        if config.get('args'):
            launch_args['args'] = config['args']

        browser = p.chromium.launch(**launch_args)

        # Create context with options
        context_opts = {}
        if config.get('user_agent'):
            context_opts['user_agent'] = config['user_agent']
        if config.get('viewport'):
            context_opts['viewport'] = config['viewport']

        if context_opts:
            context = browser.new_context(**context_opts)
            page = context.new_page()
        else:
            page = browser.new_page()

        print(f"Navigating...")
        page.goto(url, wait_until='networkidle', timeout=60000)

        # Wait for Angular to load
        print(f"Waiting for page to load...")
        page.wait_for_timeout(config.get('wait_time', 3000))

        # Try waiting for content
        try:
            page.wait_for_selector('table', timeout=10000)
            print("  ✓ Found table element")
        except:
            print("  ✗ Table not found within 10s")

        # Get HTML
        html = page.content()
        html_length = len(html)
        print(f"HTML length: {html_length:,} characters")

        # Parse with our parser
        case_data = parse_case_detail(html)

        print(f"\nParsed data:")
        print(f"  Case Type: {case_data.get('case_type')}")
        print(f"  Events: {len(case_data.get('events', []))}")
        print(f"  Parties: {len(case_data.get('parties', []))}")

        browser.close()

        return {
            'name': name,
            'html_length': html_length,
            'events': len(case_data.get('events', [])),
            'parties': len(case_data.get('parties', [])),
            'case_type': case_data.get('case_type'),
        }

def main():
    url = get_sample_case_url()
    if not url:
        print("No sample case URL found!")
        return

    print(f"Sample URL: {url}")

    configs = [
        # Baseline - headed works
        {
            'name': '1. HEADED (baseline)',
            'headless': False,
        },
        # Standard headless
        {
            'name': '2. HEADLESS (standard)',
            'headless': True,
        },
        # Headless with user-agent
        {
            'name': '3. HEADLESS + user-agent',
            'headless': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        # Headless with longer wait
        {
            'name': '4. HEADLESS + 10s wait',
            'headless': True,
            'wait_time': 10000,
        },
        # Headless with anti-detection args
        {
            'name': '5. HEADLESS + anti-detect args',
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        # Headless with viewport
        {
            'name': '6. HEADLESS + viewport 1920x1080',
            'headless': True,
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        # Try xvfb simulation with headless=False but no display
        # (this won't work without xvfb, but let's see what happens with new headless)
        {
            'name': '7. HEADLESS + all options combined',
            'headless': True,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
            ],
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'viewport': {'width': 1920, 'height': 1080},
            'wait_time': 10000,
        },
    ]

    results = []
    for config in configs:
        try:
            result = test_parsing(url, config)
            results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                'name': config['name'],
                'html_length': 0,
                'events': 0,
                'parties': 0,
                'case_type': f'ERROR: {e}',
            })

    # Compare
    print(f"\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}")
    print(f"{'Config':<40} {'HTML':>10} {'Events':>8} {'Parties':>8}")
    print("-" * 70)
    for r in results:
        status = "✓" if r['events'] > 0 else "✗"
        print(f"{status} {r['name']:<38} {r['html_length']:>10,} {r['events']:>8} {r['parties']:>8}")

    # Conclusion
    working = [r for r in results if r['events'] > 0]
    if len(working) > 1:  # More than just headed
        print(f"\n✓ Found {len(working)-1} headless configuration(s) that work!")
    else:
        print(f"\n✗ No headless configuration works. May need xvfb-run wrapper.")

if __name__ == '__main__':
    main()
