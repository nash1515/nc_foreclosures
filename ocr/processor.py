"""OCR processing for PDF documents.

Extracts text from PDFs using:
1. Direct text extraction (for text-based PDFs)
2. Tesseract OCR (for scanned/image PDFs)

The processor tries direct extraction first, falling back to OCR if needed.
"""

import os
from pathlib import Path
from typing import Optional, Tuple
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from common.logger import setup_logger
from database.connection import get_session
from database.models import Document

logger = setup_logger(__name__)


def extract_text_from_pdf(pdf_path: str) -> Tuple[str, str]:
    """
    Extract text from a PDF file.

    First attempts direct text extraction using pdftotext.
    If that yields little text, falls back to OCR.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Tuple of (extracted_text, method_used)
        method_used is either 'direct' or 'ocr'
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        return "", "error"

    # First try direct text extraction using pdftotext
    text = _extract_text_direct(pdf_path)

    # If we got substantial text, use it
    if text and len(text.strip()) > 100:
        logger.debug(f"Extracted {len(text)} chars via direct extraction")
        return text, "direct"

    # Fall back to OCR
    logger.debug("Direct extraction yielded little text, trying OCR...")
    text = _extract_text_ocr(pdf_path)

    if text:
        logger.debug(f"Extracted {len(text)} chars via OCR")
        return text, "ocr"

    return "", "failed"


def _extract_text_direct(pdf_path: str) -> str:
    """
    Extract text directly from PDF using pdftotext.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text or empty string
    """
    try:
        import subprocess
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return result.stdout
    except subprocess.TimeoutExpired:
        logger.warning(f"pdftotext timeout for {pdf_path}")
    except FileNotFoundError:
        logger.warning("pdftotext not found, install poppler-utils")
    except Exception as e:
        logger.warning(f"pdftotext failed: {e}")

    return ""


def _extract_text_ocr(pdf_path: str) -> str:
    """
    Extract text from PDF using OCR (Tesseract).

    Converts PDF pages to images, then runs OCR on each.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text or empty string
    """
    try:
        # Convert PDF pages to images
        images = convert_from_path(pdf_path, dpi=200)

        all_text = []
        for i, image in enumerate(images):
            logger.debug(f"  OCR processing page {i + 1}/{len(images)}")

            # Run OCR on the image
            text = pytesseract.image_to_string(image)
            if text:
                all_text.append(text)

        return "\n\n".join(all_text)

    except Exception as e:
        logger.error(f"OCR failed for {pdf_path}: {e}")
        return ""


def process_document(document_id: int, run_extraction: bool = True) -> bool:
    """
    Process a document by ID - extract text and update database.

    For upset_bid cases, uses Vision extraction for better accuracy.
    For other cases, uses Tesseract OCR.

    Args:
        document_id: Database ID of the document to process
        run_extraction: If True, auto-trigger data extraction after OCR

    Returns:
        bool: True if processing succeeded
    """
    case_id = None

    with get_session() as session:
        document = session.query(Document).filter_by(id=document_id).first()

        if not document:
            logger.error(f"Document not found: {document_id}")
            return False

        if not document.file_path:
            logger.warning(f"Document {document_id} has no file_path")
            return False

        # Save case_id for extraction later
        case_id = document.case_id

        # Check if already processed
        if document.ocr_text:
            logger.debug(f"Document {document_id} already has OCR text")
            return True

        logger.info(f"Processing document: {document.document_name}")

        # Get case to check classification
        from database.models import Case
        case = session.query(Case).filter_by(id=document.case_id).first()

        # Route to Vision for upset_bid cases
        if case and case.classification == 'upset_bid':
            logger.info(f"Document {document_id}: Using Vision (upset_bid case)")
            from ocr.vision_extraction import process_document_with_vision
            result = process_document_with_vision(document_id)

            # Store any text representation for compatibility
            if result.get('document_type'):
                document.ocr_text = f"[Vision extracted: {result['document_type']}]"
                session.commit()

            # Run case extraction if requested
            if run_extraction and not result.get('error'):
                _run_extraction_for_case(document.case_id)

            return not result.get('error')

        # Standard Tesseract path for non-upset_bid cases
        logger.info(f"Document {document_id}: Using Tesseract OCR")
        text, method = extract_text_from_pdf(document.file_path)

        # Check if we got usable text (minimum 50 chars)
        if not text or len(text.strip()) < 50:
            logger.warning(f"  Insufficient text extracted from {document.document_name} ({len(text) if text else 0} chars) - will retry later")
            return False

        # Save extracted text
        document.ocr_text = text
        session.commit()
        logger.info(f"  Extracted {len(text)} chars via {method}")

        # Auto-trigger data extraction and classification
        if run_extraction and case_id:
            _run_extraction_for_case(case_id)

        return True


def _run_extraction_for_case(case_id: int):
    """
    Run data extraction and classification for a case.

    Called automatically after OCR processing completes.
    Non-blocking - errors are logged but don't fail OCR.

    Args:
        case_id: Database ID of the case
    """
    try:
        from extraction.extractor import update_case_with_extracted_data
        from extraction.classifier import update_case_classification

        update_case_with_extracted_data(case_id)
        update_case_classification(case_id)

    except ImportError:
        logger.debug("Extraction module not available")
    except Exception as e:
        logger.error(f"Extraction failed for case {case_id} (non-blocking): {e}")


def process_case_documents(case_id: int) -> int:
    """
    Process all documents for a case.

    Args:
        case_id: Database ID of the case

    Returns:
        int: Number of documents successfully processed
    """
    with get_session() as session:
        documents = session.query(Document).filter_by(case_id=case_id).all()

        if not documents:
            logger.debug(f"No documents found for case {case_id}")
            return 0

        processed = 0
        for doc in documents:
            if process_document(doc.id):
                processed += 1

        return processed


def process_unprocessed_documents(limit: int = None) -> int:
    """
    Process all documents that don't have OCR text yet.

    Args:
        limit: Maximum number of documents to process (None for all)

    Returns:
        int: Number of documents processed
    """
    with get_session() as session:
        query = session.query(Document).filter(
            Document.file_path.isnot(None),
            (Document.ocr_text.is_(None) | (Document.ocr_text == ''))
        )

        if limit:
            query = query.limit(limit)

        documents = query.all()
        doc_ids = [d.id for d in documents]

    logger.info(f"Found {len(doc_ids)} documents to process")

    processed = 0
    for doc_id in doc_ids:
        try:
            if process_document(doc_id):
                processed += 1
        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")

    logger.info(f"Processed {processed}/{len(doc_ids)} documents")
    return processed
