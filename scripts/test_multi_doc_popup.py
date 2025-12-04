#!/usr/bin/env python3
"""Test script for multi-document popup handling in pdf_downloader.

Tests case 25SP000352-420 (id=1311) which has events with multiple documents.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from pathlib import Path
from database.connection import get_session
from database.models import Case
from scraper.pdf_downloader import download_all_case_documents, handle_document_selector_popup
from common.config import config
from common.logger import setup_logger

logger = setup_logger(__name__)

# Chrome user agent to avoid bot detection
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def test_multi_document_popup():
    """Test downloading documents from case with multi-document events."""

    # Get case 1311 (25SP000352-420)
    with get_session() as session:
        case = session.query(Case).filter_by(id=1311).first()
        if not case:
            print("Case 1311 not found!")
            return

        case_number = case.case_number
        case_url = case.case_url
        county = "harnett"  # 420 is Harnett County

    print(f"Testing multi-document popup handling for case {case_number}")
    print(f"URL: {case_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible for debugging
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        # Navigate to case
        print("Navigating to case page...")
        page.goto(case_url)

        # Wait for Angular app to load
        print("Waiting for page to load...")
        page.wait_for_timeout(3000)

        # Wait for events section
        try:
            page.wait_for_selector('text=Case Events', timeout=10000)
            print("Case Events section found")
        except:
            print("Warning: Could not find Case Events section")

        # Delete existing downloaded PDFs for this case to test fresh
        download_path = config.get_pdf_path(county, case_number)
        if download_path.exists():
            import shutil
            print(f"Clearing existing downloads at {download_path}")
            # Only clear files that match our test pattern
            for f in download_path.glob("11-25-2025_*"):
                print(f"  Removing: {f.name}")
                f.unlink()

        # Test downloading documents - this should handle the multi-doc popup
        print("\nTesting download_all_case_documents with popup handling...")
        downloaded = download_all_case_documents(
            page=page,
            case_id=1311,
            county=county,
            case_number=case_number,
            skip_existing=False  # Force re-download for testing
        )

        print(f"\nDownloaded {len(downloaded)} documents:")
        for doc in downloaded:
            is_new = doc.get('is_new', True)
            status = "NEW" if is_new else "EXISTING"
            print(f"  [{status}] {doc.get('event_date')} - {doc.get('event_type')}")
            print(f"          -> {Path(doc.get('file_path', '')).name}")

        # Check if we got the 11/25 upset bid documents
        nov25_docs = [d for d in downloaded if d.get('event_date') == '11/25/2025']
        if nov25_docs:
            print(f"\nSUCCESS: Got {len(nov25_docs)} documents from 11/25/2025 (multi-doc event)")
        else:
            print("\nWARNING: No documents from 11/25/2025 - popup handling may have failed")

        browser.close()


if __name__ == '__main__':
    test_multi_document_popup()
