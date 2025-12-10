#!/usr/bin/env python3
"""
Bulk OCR and address extraction for cases with missing property addresses.
"""
import sys
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

from database.connection import get_session
from database.models import Document, Case
from ocr.processor import extract_text_from_pdf
from extraction.extractor import update_case_with_extracted_data
from common.logger import setup_logger

logger = setup_logger('bulk_ocr_extract')

def main():
    # Get all cases with missing addresses - just get their IDs
    with get_session() as session:
        case_ids = [c.id for c in session.query(Case.id).filter(
            Case.property_address.is_(None)
        ).all()]

    print(f"Found {len(case_ids)} cases with missing addresses")

    ocr_count = 0
    extract_count = 0
    address_found = 0

    for i, case_id in enumerate(case_ids):
        if (i + 1) % 50 == 0:
            print(f"Processing case {i+1}/{len(case_ids)}...")

        # Use separate session for each case to avoid detachment issues
        with get_session() as session:
            # Get documents for this case that need OCR
            docs = session.query(Document).filter(
                Document.case_id == case_id,
                Document.ocr_text.is_(None),
                Document.file_path.isnot(None)
            ).all()

            # Run OCR on documents
            for doc in docs:
                doc_id = doc.id
                doc_path = doc.file_path
                try:
                    text, method = extract_text_from_pdf(doc_path)
                    if text:
                        doc.ocr_text = text
                        session.commit()
                        ocr_count += 1
                        logger.info(f"  OCR'd doc {doc_id} using {method}")
                except Exception as e:
                    logger.warning(f"OCR failed for doc {doc_id}: {e}")

        # Run extraction in its own session
        try:
            # Check if case had address before extraction
            with get_session() as check_session:
                case_before = check_session.query(Case).get(case_id)
                had_address_before = case_before.property_address is not None
                case_number = case_before.case_number

            # Run extraction
            was_updated = update_case_with_extracted_data(case_id)
            if was_updated:
                extract_count += 1

                # Check if address was found
                with get_session() as check_session:
                    case_after = check_session.query(Case).get(case_id)
                    if case_after.property_address and not had_address_before:
                        address_found += 1
                        print(f"  Found address for {case_number}: {case_after.property_address}")
        except Exception as e:
            logger.warning(f"Extraction failed for case {case_id}: {e}")

    print(f"\nSummary:")
    print(f"  Cases processed: {len(case_ids)}")
    print(f"  Documents OCR'd: {ocr_count}")
    print(f"  Extractions run: {extract_count}")
    print(f"  NEW addresses found: {address_found}")

if __name__ == '__main__':
    main()
