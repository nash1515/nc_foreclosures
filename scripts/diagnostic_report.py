#!/usr/bin/env python3
"""
Diagnostic report for upset_bid cases missing bid amounts.

Analyzes why bid amounts are missing and provides recommendations.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.connection import get_session
from database.models import Case, CaseEvent, Document
from common.logger import setup_logger

logger = setup_logger(__name__)


def generate_diagnostic_report():
    """Generate comprehensive diagnostic report."""

    print("=" * 80)
    print("DIAGNOSTIC REPORT: UPSET_BID CASES MISSING BID AMOUNTS")
    print("=" * 80)
    print()

    with get_session() as session:
        # Find all upset_bid cases missing current_bid_amount
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.current_bid_amount.is_(None)
        ).all()

        print(f"Total upset_bid cases missing bid amounts: {len(cases)}")
        print()

        for idx, case in enumerate(cases, 1):
            print(f"{idx}. Case: {case.case_number} ({case.county_name})")
            print(f"   Case ID: {case.id}")
            print(f"   Sale Date: {case.sale_date}")
            print(f"   Deadline: {case.next_bid_deadline}")
            print()

            # Check for Report of Sale event
            sale_event = session.query(CaseEvent).filter_by(
                case_id=case.id
            ).filter(
                CaseEvent.event_type.ilike('%Report%Sale%')
            ).order_by(CaseEvent.event_date.desc()).first()

            if sale_event:
                print(f"   Report of Sale Event:")
                print(f"     Date: {sale_event.event_date}")
                print(f"     Type: {sale_event.event_type}")
                print(f"     Has document URL: {'Yes' if sale_event.document_url else 'No'}")
            else:
                print(f"   No Report of Sale event found")

            print()

            # Check for Upset Bid events
            upset_events = session.query(CaseEvent).filter_by(
                case_id=case.id
            ).filter(
                CaseEvent.event_type.ilike('%Upset%Bid%')
            ).order_by(CaseEvent.event_date.desc()).all()

            if upset_events:
                print(f"   Upset Bid Events: {len(upset_events)}")
                for evt in upset_events[:3]:
                    print(f"     - {evt.event_date}: {evt.event_type}")
            else:
                print(f"   No Upset Bid events found")

            print()

            # Check documents
            docs = session.query(Document).filter_by(
                case_id=case.id
            ).filter(
                Document.ocr_text.isnot(None)
            ).all()

            print(f"   Documents with OCR: {len(docs)}")
            if docs:
                # Check unique document names
                unique_names = set(d.document_name for d in docs)
                print(f"   Unique document names: {len(unique_names)}")
                if len(unique_names) == 1:
                    print(f"     (All documents have same name: {list(unique_names)[0]})")
                    print(f"     This suggests the case PDF has been split into pages")

            print()

            # Analysis
            print(f"   DIAGNOSIS:")
            if not sale_event:
                print(f"     - Missing 'Report of Sale' event")
            elif sale_event and not docs:
                print(f"     - Sale event exists but no documents downloaded/OCR'd")
            elif docs and len(set(d.document_name for d in docs)) == 1:
                print(f"     - Only the main case petition PDF is available")
                print(f"     - Report of Sale document not yet downloaded")
            else:
                print(f"     - Documents exist but don't contain bid information")

            print()

            # Recommendation
            print(f"   RECOMMENDATION:")
            if case.sale_date and sale_event:
                print(f"     - Run scraper to download Report of Sale document")
                print(f"     - Document should be available at county website")
                print(f"     - After download, run OCR extraction")
            else:
                print(f"     - Wait for sale to occur and documents to be filed")
                print(f"     - Monitor case for new documents")

            print()
            print("-" * 80)
            print()

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("Issue: These upset_bid cases have deadlines but missing bid amounts.")
    print()
    print("Root Cause: The 'Report of Foreclosure Sale' documents containing")
    print("bid amounts have not been downloaded and OCR'd yet.")
    print()
    print("Solution Options:")
    print()
    print("1. AUTOMATIC: Run the daily scraper to re-visit these cases")
    print("   Command: ./scripts/run_daily.sh")
    print("   or: PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upset_bid")
    print()
    print("2. MANUAL: Visit each case URL and manually check for new documents")
    print()
    print("3. TEMPORARY WORKAROUND: For immediate dashboard display,")
    print("   consider showing 'Bid Amount TBD' or similar placeholder")
    print()


if __name__ == '__main__':
    generate_diagnostic_report()
