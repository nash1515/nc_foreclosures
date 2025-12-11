#!/usr/bin/env python3
"""
Fix cases missing property addresses by re-running extraction with document fallback.

This script uses the new priority-based document search to find addresses:
1. Searches documents in priority order (foreclosure notices first, then sale docs, etc.)
2. Continues to next document if current one has no property address
3. Runs OCR on documents that need it

Usage:
    PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/fix_missing_addresses.py
    PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/fix_missing_addresses.py --upset-bid-only
    PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/fix_missing_addresses.py --dry-run
"""
import sys
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

import argparse
import subprocess
from pathlib import Path

from database.connection import get_session
from database.models import Case, Document
from extraction.extractor import _find_address_in_documents, _get_document_priority
from common.logger import setup_logger

logger = setup_logger('fix_missing_addresses')


def ocr_document(file_path: str) -> str:
    """Run pdftotext on a document to get text."""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', file_path, '-'],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except Exception as e:
        logger.error(f"OCR failed for {file_path}: {e}")
        return ""


def fix_missing_addresses(upset_bid_only: bool = False, dry_run: bool = False):
    """
    Find and fix cases missing property addresses using priority-based document search.

    Args:
        upset_bid_only: If True, only process upset_bid cases
        dry_run: If True, don't actually update database
    """
    print("=" * 70)
    print("NC Foreclosures - Fix Missing Addresses (Priority-Based Search)")
    print("=" * 70)
    print()

    with get_session() as session:
        # Find cases missing addresses
        query = session.query(Case).filter(
            (Case.property_address.is_(None)) | (Case.property_address == '')
        )
        if upset_bid_only:
            query = query.filter(Case.classification == 'upset_bid')

        cases = query.all()

        print(f"Found {len(cases)} cases missing property address")
        if upset_bid_only:
            print("  (filtering to upset_bid cases only)")
        print()

        if not cases:
            print("No cases need fixing!")
            return

        fixed = 0
        still_missing = 0
        no_docs = 0

        for i, case in enumerate(cases):
            print(f"\n[{i+1}/{len(cases)}] {case.case_number} ({case.county_name})...")

            # Get all documents for this case
            documents = session.query(Document).filter_by(case_id=case.id).all()

            if not documents:
                print(f"  ⚠️  No documents found")
                no_docs += 1
                continue

            # Check how many have OCR text
            docs_with_ocr = [d for d in documents if d.ocr_text]
            docs_without_ocr = [d for d in documents if not d.ocr_text and d.file_path]

            # Sort by priority for display
            sorted_docs = sorted(documents, key=lambda d: _get_document_priority(d.file_path))

            print(f"  Documents: {len(documents)} total, {len(docs_with_ocr)} with OCR")
            print(f"  Priority order:")
            for j, doc in enumerate(sorted_docs[:5]):
                has_ocr = "✓" if doc.ocr_text else "○"
                fname = Path(doc.file_path).name if doc.file_path else doc.document_name
                print(f"    {j+1}. {has_ocr} {fname[:50]}")
            if len(sorted_docs) > 5:
                print(f"    ... and {len(sorted_docs) - 5} more")

            # OCR documents that don't have text yet (in priority order)
            docs_to_ocr = sorted(docs_without_ocr, key=lambda d: _get_document_priority(d.file_path))
            for doc in docs_to_ocr[:5]:  # Limit to 5 per case
                if not Path(doc.file_path).exists():
                    continue
                print(f"  Running OCR on {Path(doc.file_path).name}...")
                ocr_text = ocr_document(doc.file_path)
                if ocr_text and len(ocr_text) > 100:
                    if not dry_run:
                        doc.ocr_text = ocr_text
                    print(f"    Got {len(ocr_text)} chars")

            # Refresh document list after OCR
            docs_for_search = [d for d in documents if d.ocr_text]

            # Use priority-based search to find address
            address = _find_address_in_documents(docs_for_search)

            if address:
                print(f"  ✓ Found address: {address}")
                if not dry_run:
                    case.property_address = address
                fixed += 1
            else:
                print(f"  ✗ No address found in any document")
                still_missing += 1

        if not dry_run:
            session.commit()
            print("\n\nChanges committed to database")
        else:
            print("\n\n[DRY RUN - no changes made]")

        # Summary
        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total cases processed:    {len(cases)}")
        print(f"Addresses found:          {fixed}")
        print(f"Still missing:            {still_missing}")
        print(f"No documents:             {no_docs}")

        if still_missing > 0 and not upset_bid_only:
            print()
            print("Cases still missing addresses (showing upset_bid only):")
            missing_upset = [c for c in cases if not c.property_address and c.classification == 'upset_bid']
            for case in missing_upset[:10]:
                docs = session.query(Document).filter_by(case_id=case.id).count()
                print(f"  {case.case_number} ({case.county_name}) - {docs} docs")
            if len(missing_upset) > 10:
                print(f"  ... and {len(missing_upset) - 10} more")


def main():
    parser = argparse.ArgumentParser(description='Fix missing property addresses')
    parser.add_argument('--upset-bid-only', action='store_true',
                       help='Only fix upset_bid cases')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    args = parser.parse_args()

    fix_missing_addresses(
        upset_bid_only=args.upset_bid_only,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
