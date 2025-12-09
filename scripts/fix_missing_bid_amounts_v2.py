#!/usr/bin/env python3
"""
Fix missing bid amounts for upset_bid cases - Version 2.

This version uses a more reliable extraction method:
1. For Report of Sale docs, use "Minimum Amount Of Next Upset Bid" / 1.05
2. Handle OCR formatting issues better
"""

import sys
from decimal import Decimal
from pathlib import Path
import re

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.connection import get_session
from database.models import Case, Document
from extraction.extractor import (
    is_report_of_sale_document,
    is_upset_bid_document
)
from common.logger import setup_logger

logger = setup_logger(__name__)


def extract_minimum_next_upset_from_report(ocr_text):
    """
    Extract "Minimum Amount Of Next Upset Bid" from Report of Sale.
    This is more reliable than the handwritten bid amount field.
    """
    if not ocr_text:
        return None

    # Pattern for "Minimum Amount Of Next Upset Bid"
    patterns = [
        r'Minimum\s+Amount\s+Of\s+Next\s+Upset\s+Bid[\s\S]{0,100}?\$\s*([\d,]+\.?\d*)',
        r'Minimum\s+Amount[\s\S]{0,50}?Next[\s\S]{0,50}?Upset[\s\S]{0,50}?\$\s*([\d,]+\.?\d*)',
    ]

    for pattern in patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '').replace(' ', '')
            try:
                return Decimal(amount_str)
            except:
                continue

    return None


def fix_missing_bid_amounts():
    """Find and fix missing bid amounts."""

    results = {
        'total_missing': 0,
        'fixed': [],
        'needs_attention': []
    }

    print("=" * 80)
    print("FIXING MISSING BID AMOUNTS - VERSION 2")
    print("Using Minimum Next Upset Bid field for calculation")
    print("=" * 80)
    print()

    with get_session() as session:
        # Find all upset_bid cases missing current_bid_amount
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.current_bid_amount.is_(None)
        ).all()

        results['total_missing'] = len(cases)
        print(f"Found {len(cases)} upset_bid cases missing current_bid_amount")
        print()

        for case in cases:
            print(f"Case: {case.case_number} ({case.county_name}) - ID: {case.id}")
            print(f"  Deadline: {case.next_bid_deadline}")

            # Get all documents with OCR text
            documents = session.query(Document).filter(
                Document.case_id == case.id,
                Document.ocr_text.isnot(None)
            ).all()

            print(f"  Documents with OCR: {len(documents)}")

            # Try to extract bid amount
            extracted_bid = None
            source_doc = None
            method = None

            for doc in documents:
                # Check for Report of Sale
                if is_report_of_sale_document(doc.ocr_text):
                    print(f"  Found Report of Sale: {doc.document_name}")

                    # Extract "Minimum Amount Of Next Upset Bid"
                    min_next = extract_minimum_next_upset_from_report(doc.ocr_text)
                    if min_next:
                        # Calculate current bid: min_next / 1.05
                        calculated_bid = round(min_next / Decimal('1.05'), 2)
                        print(f"    Minimum next upset bid: ${min_next}")
                        print(f"    Calculated current bid: ${calculated_bid}")
                        extracted_bid = calculated_bid
                        source_doc = doc.document_name
                        method = "Calculated from Minimum Next Upset"
                        break

                # Check for Upset Bid Notice (has more current bid)
                if is_upset_bid_document(doc.ocr_text):
                    print(f"  Found Upset Bid Notice: {doc.document_name}")

                    # Try to extract minimum next from upset bid doc too
                    min_next = extract_minimum_next_upset_from_report(doc.ocr_text)
                    if min_next:
                        calculated_bid = round(min_next / Decimal('1.05'), 2)
                        print(f"    Minimum next upset bid: ${min_next}")
                        print(f"    Calculated current bid: ${calculated_bid}")
                        extracted_bid = calculated_bid
                        source_doc = doc.document_name
                        method = "Calculated from Upset Bid Notice"
                        # Don't break - keep looking for later upset bids

            # Update the case if we found a bid amount
            if extracted_bid:
                case.current_bid_amount = extracted_bid
                case.minimum_next_bid = round(extracted_bid * Decimal('1.05'), 2)

                print(f"  UPDATED:")
                print(f"    Current bid: ${case.current_bid_amount}")
                print(f"    Minimum next: ${case.minimum_next_bid}")
                print(f"    Method: {method}")
                print(f"    Source: {source_doc}")

                results['fixed'].append({
                    'case_number': case.case_number,
                    'case_id': case.id,
                    'county': case.county_name,
                    'current_bid': float(case.current_bid_amount),
                    'minimum_next_bid': float(case.minimum_next_bid),
                    'method': method,
                    'source': source_doc
                })
            else:
                print(f"  Could not extract bid amount")
                results['needs_attention'].append({
                    'case_number': case.case_number,
                    'case_id': case.id,
                    'county': case.county_name
                })

            print()

        # Commit all changes
        session.commit()

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total missing: {results['total_missing']}")
    print(f"Fixed: {len(results['fixed'])}")
    print(f"Still need attention: {len(results['needs_attention'])}")
    print()

    if results['fixed']:
        print("FIXED CASES:")
        for item in results['fixed']:
            print(f"  {item['case_number']} ({item['county']})")
            print(f"    Current bid: ${item['current_bid']:,.2f}")
            print(f"    Minimum next: ${item['minimum_next_bid']:,.2f}")
            print(f"    Method: {item['method']}")
        print()

    return results


if __name__ == '__main__':
    try:
        results = fix_missing_bid_amounts()
        sys.exit(0 if len(results['fixed']) > 0 else 1)
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        sys.exit(2)
