#!/usr/bin/env python3
"""
Clean up duplicate documents and rename unknown files.
"""
import sys
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

import os
from pathlib import Path
from database.connection import get_session
from database.models import Document, Case
from common.logger import setup_logger

logger = setup_logger('cleanup_docs')

def remove_duplicate_db_entries():
    """Remove duplicate document entries keeping the one with OCR text if available."""
    with get_session() as session:
        # Find duplicates
        from sqlalchemy import func
        duplicates = session.query(
            Document.case_id,
            Document.document_name,
            func.count(Document.id).label('cnt')
        ).group_by(
            Document.case_id,
            Document.document_name
        ).having(func.count(Document.id) > 1).all()

        print(f"Found {len(duplicates)} duplicate groups")

        removed = 0
        for case_id, doc_name, cnt in duplicates:
            # Get all docs with this name for this case
            docs = session.query(Document).filter(
                Document.case_id == case_id,
                Document.document_name == doc_name
            ).order_by(Document.id).all()

            # Keep the first one with OCR text, or just the first one
            keep_doc = None
            for d in docs:
                if d.ocr_text:
                    keep_doc = d
                    break
            if not keep_doc:
                keep_doc = docs[0]

            # Delete the rest
            for d in docs:
                if d.id != keep_doc.id:
                    logger.info(f"Removing duplicate: case_id={case_id}, doc={doc_name}, id={d.id}")
                    session.delete(d)
                    removed += 1

        session.commit()
        print(f"Removed {removed} duplicate entries")
        return removed

def main():
    print("=== Document Cleanup ===\n")

    # Step 1: Remove duplicate DB entries
    print("Step 1: Removing duplicate database entries...")
    removed = remove_duplicate_db_entries()

    # Verify
    with get_session() as session:
        total = session.query(Document).count()
        print(f"\nTotal documents after cleanup: {total}")

        # Check for remaining duplicates
        from sqlalchemy import func
        duplicates = session.query(
            Document.case_id,
            Document.document_name,
            func.count(Document.id).label('cnt')
        ).group_by(
            Document.case_id,
            Document.document_name
        ).having(func.count(Document.id) > 1).all()

        if duplicates:
            print(f"\nWARNING: Still have {len(duplicates)} duplicate groups!")
        else:
            print("\nSUCCESS: No duplicates remaining!")

if __name__ == '__main__':
    main()
