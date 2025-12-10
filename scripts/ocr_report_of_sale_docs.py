#!/usr/bin/env python3
"""
Run OCR on sale-related documents for upset_bid cases.
Processes: Report of Sale, Affidavits, and Notice documents that may contain addresses.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import or_

from database.connection import get_session
from database.models import Document, Case
from ocr.processor import process_document
from common.logger import setup_logger

logger = setup_logger(__name__)


def main():
    print("=" * 80)
    print("RUNNING OCR ON SALE-RELATED DOCUMENTS")
    print("=" * 80)
    print()

    # Find upset_bid cases missing bid amounts
    case_ids = []
    with get_session() as session:
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.current_bid_amount.is_(None)
        ).all()

        case_ids = [c.id for c in cases]
        print(f"Found {len(case_ids)} upset_bid cases missing bid amounts")
        print(f"Case IDs: {case_ids}")
        print()

    # Find relevant documents for these cases without OCR
    with get_session() as session:
        docs = session.query(Document).filter(
            Document.case_id.in_(case_ids),
            or_(
                Document.document_name.ilike('%Report Of Foreclosure Sale%'),
                Document.document_name.ilike('%Report of Sale%'),
                Document.document_name.ilike('%Allowing Foreclosure Sale%'),
                Document.document_name.ilike('%Affidavit%'),
                Document.document_name.ilike('%Notice of Sale%'),
                Document.document_name.ilike('%Notice of Foreclosure Sale%')
            ),
            Document.ocr_text.is_(None),
            Document.file_path.isnot(None)
        ).all()

        print(f"Found {len(docs)} documents without OCR (Report of Sale, Affidavits, Notices)")
        print()

        processed = 0
        for doc in docs:
            print(f"Processing: {doc.document_name} (Doc ID: {doc.id}, Case ID: {doc.case_id})")
            print(f"  File path: {doc.file_path}")

            # Check if file exists
            file_path = Path(doc.file_path)
            if not file_path.exists():
                print(f"  ERROR: File not found")
                continue

            # Process the document
            try:
                success = process_document(doc.id)
                if success:
                    print(f"  SUCCESS: OCR completed")
                    processed += 1
                else:
                    print(f"  FAILED: OCR failed")
            except Exception as e:
                print(f"  ERROR: {e}")

            print()

    print("=" * 80)
    print(f"OCR COMPLETE: Processed {processed} / {len(docs)} documents")
    print("=" * 80)


if __name__ == '__main__':
    main()
