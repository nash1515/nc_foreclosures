#!/usr/bin/env python3
"""Debug script for Durham scraper."""
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(30000)

    print('Navigating to Durham portal...')
    page.goto('https://taxcama.dconc.gov/camapwa/')

    print('Page loaded, waiting 2s...')
    time.sleep(2)

    print('Looking for street num input...')
    street_num = page.locator('#ContentPlaceHolder1_StreetNumTextBox')
    print(f'Street num visible: {street_num.is_visible()}')

    print('Looking for street name input...')
    street_name = page.locator('#ContentPlaceHolder1_StreetNameTextBox')
    print(f'Street name visible: {street_name.is_visible()}')

    print('Looking for search button...')
    search_btn = page.locator('#ContentPlaceHolder1_AddressButton')
    print(f'Search button visible: {search_btn.is_visible()}')

    print('Filling fields...')
    street_num.fill('1806')
    street_name.fill('BIRMINGHAM')

    print('Clicking search...')
    search_btn.click()

    print('Waiting for network idle...')
    page.wait_for_load_state('networkidle', timeout=30000)

    print('Checking for results table...')
    results = page.locator('#ContentPlaceHolder1_ResultsGridView')
    print(f'Results visible: {results.is_visible()}')

    if results.is_visible():
        rows = results.locator('tr').all()
        print(f'Found {len(rows)} rows')

    print('Checking for no records message...')
    no_records = page.locator('text=No records found')
    print(f'No records message visible: {no_records.is_visible()}')

    print('Waiting 5s for manual inspection...')
    time.sleep(5)

    browser.close()
    print('Done!')
