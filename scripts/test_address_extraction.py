#!/usr/bin/env python3
"""
Test script for updated address extraction patterns.
Tests two specific cases:
1. 25SP001154-910 (Wake County) - Should extract HOA lien address
2. 25SP000628-310 (Durham County) - Should reject attorney address
"""

import sys
from sqlalchemy.orm import Session
from database.connection import get_db_session
from database.models import Case, Document
from extraction.extractor import extract_property_address

def test_case_address_extraction(session: Session, case_number: str, county_code: str):
    """Test address extraction for a specific case."""
    print(f"\n{'='*80}")
    print(f"Testing Case: {case_number} ({county_code})")
    print(f"{'='*80}")

    # Find the case
    case = session.query(Case).filter(
        Case.case_number == case_number,
        Case.county_code == county_code
    ).first()

    if not case:
        print(f"❌ Case not found: {case_number}")
        return

    print(f"✓ Found case ID: {case.id}")
    print(f"  Current property_address in DB: {case.property_address or 'NULL'}")

    # Get all documents with OCR text
    documents = session.query(Document).filter(
        Document.case_id == case.id,
        Document.ocr_text.isnot(None),
        Document.ocr_text != ''
    ).all()

    print(f"  Found {len(documents)} documents with OCR text")

    if not documents:
        print("❌ No OCR text available for this case")
        return

    # Test address extraction on each document
    addresses_found = []
    for doc in documents:
        print(f"\n  Document ID: {doc.id} - {doc.document_name or 'unnamed'}")
        print(f"  OCR text length: {len(doc.ocr_text)} characters")

        # Show relevant snippets
        ocr_lower = doc.ocr_text.lower()
        if 'upon' in ocr_lower:
            # Find and show "upon" context
            idx = ocr_lower.find('upon')
            start = max(0, idx - 50)
            end = min(len(doc.ocr_text), idx + 150)
            snippet = doc.ocr_text[start:end].replace('\n', ' ')
            print(f"  'upon' context: ...{snippet}...")

        if 'attorney' in ocr_lower or 'law' in ocr_lower:
            print(f"  ⚠️  Document contains 'attorney' or 'law' - may have attorney address")

        # Extract address
        address = extract_property_address(doc.ocr_text)

        if address:
            print(f"  ✓ Extracted: {address}")
            addresses_found.append({
                'doc_id': doc.id,
                'document_name': doc.document_name,
                'address': address
            })
        else:
            print(f"  ✗ No address extracted")

    # Summary
    print(f"\n  {'─'*76}")
    print(f"  SUMMARY for {case_number}:")
    if addresses_found:
        print(f"  ✓ Found {len(addresses_found)} address(es):")
        for item in addresses_found:
            print(f"    - Doc {item['doc_id']}: {item['address']}")
    else:
        print(f"  ✗ No addresses extracted from any document")

    return addresses_found

def main():
    """Run tests on both cases."""
    print("Testing Updated Address Extraction Patterns")
    print("=" * 80)

    with get_db_session() as session:
        # Test Case 1: Should extract HOA lien address
        print("\n\nTEST 1: HOA Lien Address (should extract)")
        case1_results = test_case_address_extraction(
            session,
            case_number="25SP001154-910",
            county_code="910"
        )

        # Test Case 2: Should reject attorney address
        print("\n\nTEST 2: Attorney Address (should reject)")
        case2_results = test_case_address_extraction(
            session,
            case_number="25SP000628-310",
            county_code="310"
        )

        # Final assessment
        print("\n\n" + "=" * 80)
        print("FINAL ASSESSMENT")
        print("=" * 80)

        print("\nCase 25SP001154-910 (Wake County):")
        if case1_results:
            print(f"  ✓ SUCCESS - Extracted: {case1_results[0]['address']}")
            if '4317 Scaup Court' in case1_results[0]['address']:
                print(f"  ✓✓ CORRECT - Matched expected HOA lien address")
            else:
                print(f"  ⚠️  WARNING - Address doesn't match expected pattern")
        else:
            print(f"  ✗ FAILED - No address extracted (expected HOA lien address)")

        print("\nCase 25SP000628-310 (Durham County):")
        if case2_results:
            extracted = case2_results[0]['address']
            if 'Oleander' in extracted or 'Wilmington' in extracted:
                print(f"  ✗ FAILED - Still extracting attorney address: {extracted}")
            else:
                print(f"  ⚠️  PARTIAL - Extracted different address: {extracted}")
                print(f"     (Need to verify if this is the actual property)")
        else:
            print(f"  ✓ SUCCESS - Rejected attorney address (no address extracted)")
            print(f"     This is correct behavior if no property address exists in OCR text")

if __name__ == "__main__":
    main()
