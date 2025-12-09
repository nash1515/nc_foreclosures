#!/usr/bin/env python3
"""
Fix missing bid amounts for upset_bid cases.

This script:
1. Finds all upset_bid cases missing current_bid_amount
2. Examines their documents for OCR text
3. Extracts bid amounts using existing extraction functions
4. Updates the database with extracted values
5. Reports results
"""

import sys
from decimal import Decimal
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.connection import get_session
from database.models import Case, Document
from extraction.extractor import (
    extract_upset_bid_data,
    extract_report_of_sale_data,
    is_report_of_sale_document,
    is_upset_bid_document
)
from common.logger import setup_logger

logger = setup_logger(__name__)


def fix_missing_bid_amounts():
    """
    Find upset_bid cases missing bid amounts and try to extract them from documents.

    Returns:
        dict: Summary of results
    """
    results = {
        'total_missing': 0,
        'fixed': [],
        'needs_attention': [],
        'no_documents': [],
        'no_ocr': []
    }

    print("=" * 80)
    print("FIXING MISSING BID AMOUNTS FOR UPSET_BID CASES")
    print("=" * 80)
    print()

    # Find all upset_bid cases missing current_bid_amount
    with get_session() as session:
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.current_bid_amount.is_(None)
        ).all()

        results['total_missing'] = len(cases)
        print(f"Found {len(cases)} upset_bid cases missing current_bid_amount")
        print()

        if len(cases) == 0:
            print("No cases need fixing!")
            return results

        # Process each case
        for case in cases:
            print(f"Processing Case: {case.case_number} ({case.county_name})")
            print(f"  Case ID: {case.id}")
            print(f"  Classification: {case.classification}")
            print(f"  Current bid: {case.current_bid_amount}")
            print(f"  Deadline: {case.next_bid_deadline}")

            # Get documents with OCR text
            documents = session.query(Document).filter(
                Document.case_id == case.id,
                Document.ocr_text.isnot(None)
            ).all()

            if not documents:
                print(f"  No documents found for case {case.case_number}")
                results['no_documents'].append({
                    'case_number': case.case_number,
                    'case_id': case.id,
                    'county': case.county_name
                })
                print()
                continue

            print(f"  Found {len(documents)} documents with OCR text")

            # Try to extract bid amounts from documents
            extracted_bid = None
            extracted_from_doc = None

            for doc in documents:
                if not doc.ocr_text:
                    continue

                print(f"  Checking document: {doc.document_name}")

                # Check if it's a Report of Sale (initial bid)
                if is_report_of_sale_document(doc.ocr_text):
                    print(f"    Identified as Report of Foreclosure Sale")
                    sale_data = extract_report_of_sale_data(doc.ocr_text)
                    if sale_data.get('initial_bid'):
                        print(f"    Found initial bid: ${sale_data['initial_bid']}")
                        extracted_bid = sale_data['initial_bid']
                        extracted_from_doc = doc.document_name
                        # Keep looking for upset bid docs (they're more current)

                # Check if it's an Upset Bid Notice (more current bid)
                if is_upset_bid_document(doc.ocr_text):
                    print(f"    Identified as Notice of Upset Bid")
                    upset_data = extract_upset_bid_data(doc.ocr_text)

                    # The "current_bid" in an upset bid doc is the NEW bid being filed
                    # This is the most current bid amount
                    if upset_data.get('current_bid'):
                        print(f"    Found current bid: ${upset_data['current_bid']}")
                        extracted_bid = upset_data['current_bid']
                        extracted_from_doc = doc.document_name
                        # This is the most current, use this
                        break
                    elif upset_data.get('previous_bid'):
                        print(f"    Found previous bid: ${upset_data['previous_bid']}")
                        if not extracted_bid:
                            extracted_bid = upset_data['previous_bid']
                            extracted_from_doc = doc.document_name

            # Update the case if we found a bid amount
            if extracted_bid:
                case.current_bid_amount = extracted_bid
                # NC law: minimum next bid is current_bid * 1.05
                case.minimum_next_bid = round(extracted_bid * Decimal('1.05'), 2)

                print(f"  UPDATED:")
                print(f"    Current bid: ${case.current_bid_amount}")
                print(f"    Minimum next bid: ${case.minimum_next_bid}")
                print(f"    Source: {extracted_from_doc}")

                results['fixed'].append({
                    'case_number': case.case_number,
                    'case_id': case.id,
                    'county': case.county_name,
                    'current_bid': float(case.current_bid_amount),
                    'minimum_next_bid': float(case.minimum_next_bid),
                    'source_doc': extracted_from_doc
                })
            else:
                print(f"  Could not extract bid amount from {len(documents)} documents")
                results['needs_attention'].append({
                    'case_number': case.case_number,
                    'case_id': case.id,
                    'county': case.county_name,
                    'num_documents': len(documents),
                    'document_names': [d.document_name for d in documents]
                })

            print()

        # Commit all changes
        session.commit()

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total upset_bid cases missing bid amounts: {results['total_missing']}")
    print(f"Successfully fixed: {len(results['fixed'])}")
    print(f"Need manual attention: {len(results['needs_attention'])}")
    print(f"No documents: {len(results['no_documents'])}")
    print()

    if results['fixed']:
        print("FIXED CASES:")
        print("-" * 80)
        for item in results['fixed']:
            print(f"  {item['case_number']} ({item['county']})")
            print(f"    Current bid: ${item['current_bid']:,.2f}")
            print(f"    Minimum next: ${item['minimum_next_bid']:,.2f}")
            print(f"    Source: {item['source_doc']}")
            print()

    if results['needs_attention']:
        print("NEED MANUAL ATTENTION:")
        print("-" * 80)
        for item in results['needs_attention']:
            print(f"  {item['case_number']} ({item['county']})")
            print(f"    Case ID: {item['case_id']}")
            print(f"    Documents ({item['num_documents']}): {', '.join(item['document_names'])}")
            print()

    if results['no_documents']:
        print("NO DOCUMENTS FOUND:")
        print("-" * 80)
        for item in results['no_documents']:
            print(f"  {item['case_number']} ({item['county']}) - Case ID: {item['case_id']}")
        print()

    return results


if __name__ == '__main__':
    try:
        results = fix_missing_bid_amounts()

        # Exit with appropriate code
        if results['total_missing'] == 0:
            sys.exit(0)
        elif len(results['fixed']) == results['total_missing']:
            print("All cases successfully fixed!")
            sys.exit(0)
        else:
            print(f"{len(results['needs_attention']) + len(results['no_documents'])} cases still need attention")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        sys.exit(2)
