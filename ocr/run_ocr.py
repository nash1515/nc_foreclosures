#!/usr/bin/env python3
"""Standalone OCR processing script.

Run OCR on downloaded PDFs independently from the scraper.

Usage:
    # Process all unprocessed documents
    python ocr/run_ocr.py

    # Process specific case by ID
    python ocr/run_ocr.py --case-id 123

    # Process specific document by ID
    python ocr/run_ocr.py --document-id 456

    # Limit number of documents to process
    python ocr/run_ocr.py --limit 10

    # Reprocess all documents (even those with OCR text)
    python ocr/run_ocr.py --reprocess
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.logger import setup_logger
from database.connection import get_session
from database.models import Document
from ocr.processor import (
    process_document,
    process_case_documents,
    process_unprocessed_documents
)

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Run OCR processing on downloaded PDFs')

    parser.add_argument('--case-id', type=int, help='Process documents for a specific case')
    parser.add_argument('--document-id', type=int, help='Process a specific document')
    parser.add_argument('--limit', type=int, help='Limit number of documents to process')
    parser.add_argument('--reprocess', action='store_true',
                        help='Reprocess documents that already have OCR text')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("OCR PROCESSING")
    logger.info("=" * 60)

    if args.document_id:
        # Process single document
        logger.info(f"Processing document ID: {args.document_id}")

        if args.reprocess:
            # Clear existing OCR text first
            with get_session() as session:
                doc = session.query(Document).filter_by(id=args.document_id).first()
                if doc:
                    doc.ocr_text = None
                    session.commit()

        success = process_document(args.document_id)
        if success:
            logger.info("Document processed successfully")
        else:
            logger.error("Document processing failed")
        sys.exit(0 if success else 1)

    elif args.case_id:
        # Process all documents for a case
        logger.info(f"Processing documents for case ID: {args.case_id}")

        if args.reprocess:
            with get_session() as session:
                docs = session.query(Document).filter_by(case_id=args.case_id).all()
                for doc in docs:
                    doc.ocr_text = None
                session.commit()

        count = process_case_documents(args.case_id)
        logger.info(f"Processed {count} documents")
        sys.exit(0)

    else:
        # Process unprocessed documents
        if args.reprocess:
            logger.info("Reprocessing ALL documents...")
            with get_session() as session:
                query = session.query(Document).filter(Document.file_path.isnot(None))
                if args.limit:
                    query = query.limit(args.limit)
                docs = query.all()
                for doc in docs:
                    doc.ocr_text = None
                session.commit()
                logger.info(f"Cleared OCR text from {len(docs)} documents")

        logger.info(f"Processing unprocessed documents (limit: {args.limit or 'none'})...")
        count = process_unprocessed_documents(limit=args.limit)
        logger.info("=" * 60)
        logger.info(f"OCR COMPLETE - Processed {count} documents")
        logger.info("=" * 60)
        sys.exit(0)


if __name__ == '__main__':
    main()
