#!/usr/bin/env python3
"""Re-extract property addresses from existing OCR text.

This script processes cases that have OCR'd documents but are missing
property addresses. It runs the updated extraction patterns against
all document text for each case.

Usage:
    PYTHONPATH=$(pwd) venv/bin/python scripts/extract_addresses.py
    PYTHONPATH=$(pwd) venv/bin/python scripts/extract_addresses.py --dry-run
    PYTHONPATH=$(pwd) venv/bin/python scripts/extract_addresses.py --limit 100
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_session
from database.models import Case, Document
from extraction.extractor import extract_property_address
from common.logger import setup_logger

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Re-extract property addresses from OCR text')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without saving')
    parser.add_argument('--limit', type=int, help='Limit number of cases to process')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all attempts, not just successes')
    args = parser.parse_args()

    print("=" * 60)
    print("Property Address Re-extraction")
    print("=" * 60)

    with get_session() as session:
        # Get current stats
        total_cases = session.query(Case).count()
        cases_with_address = session.query(Case).filter(Case.property_address != None).count()
        print(f"\nBefore: {cases_with_address}/{total_cases} cases have addresses ({cases_with_address*100//total_cases}%)")

        # Find cases with OCR but no address
        subquery = session.query(Document.case_id).filter(
            Document.ocr_text != None
        ).distinct().subquery()

        query = session.query(Case).filter(
            Case.property_address == None,
            Case.id.in_(subquery)
        )

        if args.limit:
            query = query.limit(args.limit)

        cases = query.all()
        print(f"Found {len(cases)} cases with OCR text but no address\n")

        updated = 0
        failed = 0

        for case in cases:
            # Get all OCR text for this case
            docs = session.query(Document).filter(
                Document.case_id == case.id,
                Document.ocr_text != None
            ).all()

            # Combine all document text
            combined_text = "\n\n".join(d.ocr_text for d in docs if d.ocr_text)

            # Try to extract address
            address = extract_property_address(combined_text)

            if address:
                if not args.dry_run:
                    case.property_address = address
                updated += 1
                print(f"  [OK] {case.case_number}: {address}")
            else:
                failed += 1
                if args.verbose:
                    print(f"  [--] {case.case_number}: No address found ({len(docs)} docs)")

        if not args.dry_run and updated > 0:
            session.commit()
            print(f"\n{'=' * 60}")
            print(f"COMMITTED: Updated {updated} cases with addresses")
        elif args.dry_run:
            print(f"\n{'=' * 60}")
            print(f"DRY RUN: Would update {updated} cases")
        else:
            print(f"\n{'=' * 60}")
            print(f"No updates needed")

        print(f"Failed to extract: {failed} cases")

        # Show after stats
        if not args.dry_run:
            cases_with_address_after = session.query(Case).filter(Case.property_address != None).count()
            print(f"\nAfter: {cases_with_address_after}/{total_cases} cases have addresses ({cases_with_address_after*100//total_cases}%)")
            print(f"Improvement: +{cases_with_address_after - cases_with_address} addresses")


if __name__ == "__main__":
    main()
