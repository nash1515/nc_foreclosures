#!/usr/bin/env python3
"""Test case monitor on a single upset_bid case with PDF document download."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import Case
from scraper.case_monitor import CaseMonitor

def main():
    case_number = sys.argv[1] if len(sys.argv) > 1 else '24SP001280-670'

    print(f"Testing case monitor on case: {case_number}")

    # Get the case
    with get_session() as session:
        case = session.query(Case).filter_by(case_number=case_number).first()
        if not case:
            print(f"Case not found: {case_number}")
            return

        print(f"  Case ID: {case.id}")
        print(f"  Classification: {case.classification}")
        print(f"  Current bid: {case.current_bid_amount}")
        print(f"  URL: {case.case_url[:80]}...")

        # Detach from session
        session.expunge(case)

    # Create monitor with single worker
    monitor = CaseMonitor(max_workers=1, headless=False)

    # Run on single case
    print("\nRunning case monitor...")
    results = monitor.run(cases=[case])

    print("\nResults:")
    print(f"  Cases checked: {results.get('cases_checked', 0)}")
    print(f"  Events added: {results.get('events_added', 0)}")
    print(f"  Bid updates: {results.get('bid_updates', 0)}")
    print(f"  Errors: {results.get('errors', [])}")

    # Check updated case
    with get_session() as session:
        case = session.query(Case).filter_by(case_number=case_number).first()
        print(f"\nUpdated case data:")
        print(f"  Current bid: ${case.current_bid_amount}")
        print(f"  Minimum next bid: ${case.minimum_next_bid}")
        print(f"  Next deadline: {case.next_bid_deadline}")

        # Count documents
        from database.models import Document
        doc_count = session.query(Document).filter_by(case_id=case.id).count()
        print(f"  Documents: {doc_count}")

if __name__ == '__main__':
    main()
