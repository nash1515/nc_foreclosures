"""
Vision extraction module for structured data extraction from PDFs.

Uses Claude Vision to extract structured data from foreclosure documents.
This is the primary extraction method for upset_bid cases.
"""
import os
import json
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime

import anthropic
from pdf2image import convert_from_path
import base64
import io

from common.logger import setup_logger

logger = setup_logger(__name__)

VISION_MODEL = "claude-sonnet-4-20250514"
MAX_PAGES = 3  # First 3 pages + last if >3

EXTRACTION_PROMPT = """You are extracting structured data from a North Carolina foreclosure document.

Analyze this document image and extract the following fields. Return ONLY valid JSON with these exact keys:

{
    "property_address": "Full street address with city, state, zip - or null if not found",
    "legal_description": "Legal property description (lot/block/subdivision) - or null if not found",
    "bid_amount": <number - winning/current bid amount in dollars, no $ sign - or null>,
    "minimum_next_bid": <number - minimum amount for next upset bid - or null>,
    "deposit_required": <number - required deposit amount - or null>,
    "sale_date": "YYYY-MM-DD format - date of foreclosure sale - or null",
    "trustee_name": "Name of substitute trustee - or null",
    "attorney_name": "Foreclosure attorney name - or null",
    "attorney_phone": "Attorney phone number - or null",
    "attorney_email": "Attorney email address - or null",
    "document_type": "Your assessment of document type (Report of Foreclosure Sale, Notice of Upset Bid, etc.)",
    "confidence": "high/medium/low - your confidence in the extraction accuracy",
    "notes": "Any issues or uncertainties - or null"
}

IMPORTANT:
- Return null for any field you cannot find or are uncertain about
- Do NOT guess or infer missing information
- For amounts, extract the numeric value only (no $ or commas)
- For addresses, include full address if available (street, city, state, zip)
- Property addresses often appear after "property located at" or "Property Address"
- Bid amounts often appear after "Amount Bid" or "Highest Bid"

Return ONLY the JSON object, no other text."""


def _pdf_to_base64_images(pdf_path: str, max_pages: int = MAX_PAGES) -> list:
    """Convert PDF pages to base64-encoded PNG images."""
    try:
        images = convert_from_path(pdf_path, dpi=200)

        # If more than max_pages, take first (max-1) + last
        if len(images) > max_pages:
            selected = images[:max_pages-1] + [images[-1]]
        else:
            selected = images[:max_pages]

        base64_images = []
        for img in selected:
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            base64_images.append(base64.b64encode(buffer.getvalue()).decode('utf-8'))

        return base64_images
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        return []


def extract_structured_data(pdf_path: str) -> Dict[str, Any]:
    """
    Extract structured data from a PDF using Claude Vision.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dict with extracted fields. Missing fields are None.
        Includes 'error' key if extraction failed.
        Includes 'cost_cents' and 'tokens' for tracking.
    """
    result = {
        'property_address': None,
        'legal_description': None,
        'bid_amount': None,
        'minimum_next_bid': None,
        'deposit_required': None,
        'sale_date': None,
        'trustee_name': None,
        'attorney_name': None,
        'attorney_phone': None,
        'attorney_email': None,
        'document_type': None,
        'confidence': None,
        'notes': None,
        'error': None,
        'cost_cents': 0,
        'tokens': {'input': 0, 'output': 0}
    }

    # Convert PDF to images
    images = _pdf_to_base64_images(pdf_path)
    if not images:
        result['error'] = "Failed to convert PDF to images"
        return result

    # Build message content with images
    content = []
    for i, img_base64 in enumerate(images):
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_base64
            }
        })
    content.append({"type": "text", "text": EXTRACTION_PROMPT})

    try:
        client = anthropic.Anthropic()

        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}]
        )

        # Track usage
        result['tokens'] = {
            'input': response.usage.input_tokens,
            'output': response.usage.output_tokens
        }
        # Rough cost estimate: $3/M input, $15/M output for Sonnet
        result['cost_cents'] = (
            (response.usage.input_tokens * 0.003 / 10) +
            (response.usage.output_tokens * 0.015 / 10)
        )

        # Parse JSON response
        response_text = response.content[0].text.strip()

        # Handle markdown code blocks
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]

        data = json.loads(response_text)

        # Map extracted data to result
        result['property_address'] = data.get('property_address')
        result['legal_description'] = data.get('legal_description')
        result['sale_date'] = data.get('sale_date')
        result['trustee_name'] = data.get('trustee_name')
        result['attorney_name'] = data.get('attorney_name')
        result['attorney_phone'] = data.get('attorney_phone')
        result['attorney_email'] = data.get('attorney_email')
        result['document_type'] = data.get('document_type')
        result['confidence'] = data.get('confidence')
        result['notes'] = data.get('notes')

        # Convert numeric fields to Decimal
        if data.get('bid_amount') is not None:
            result['bid_amount'] = Decimal(str(data['bid_amount']))
        if data.get('minimum_next_bid') is not None:
            result['minimum_next_bid'] = Decimal(str(data['minimum_next_bid']))
        if data.get('deposit_required') is not None:
            result['deposit_required'] = Decimal(str(data['deposit_required']))

        logger.info(f"Vision extraction complete: {result['document_type']}, confidence={result['confidence']}")

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        result['error'] = f"API error: {str(e)}"
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Vision response as JSON: {e}")
        result['error'] = f"JSON parse error: {str(e)}"
    except Exception as e:
        logger.error(f"Vision extraction failed: {e}")
        result['error'] = f"Extraction error: {str(e)}"

    return result


def process_document_with_vision(document_id: int) -> Dict[str, Any]:
    """
    Process a single document with Vision and update tracking.

    Args:
        document_id: Database ID of the document

    Returns:
        Extraction result dict
    """
    from database.connection import get_session
    from database.models import Document

    with get_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            return {'error': f'Document {document_id} not found'}

        if not doc.file_path or not os.path.exists(doc.file_path):
            return {'error': f'PDF file not found: {doc.file_path}'}

        # Extract data
        result = extract_structured_data(doc.file_path)

        # Update tracking timestamp
        doc.vision_processed_at = datetime.utcnow()
        session.commit()

        logger.info(f"Document {document_id} processed with Vision (cost: ${result['cost_cents']:.2f})")

    return result


def sweep_case_documents(case_id: int, force: bool = False) -> Dict[str, Any]:
    """
    Process all documents for a case with Vision.

    Args:
        case_id: Database ID of the case
        force: If True, reprocess even if already processed

    Returns:
        Dict with 'documents_processed', 'total_cost_cents', 'results'
    """
    from database.connection import get_session
    from database.models import Document, Case

    summary = {
        'documents_processed': 0,
        'documents_skipped': 0,
        'total_cost_cents': 0,
        'results': [],
        'errors': []
    }

    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            summary['errors'].append(f'Case {case_id} not found')
            return summary

        # Get documents to process
        query = session.query(Document).filter_by(case_id=case_id)
        if not force:
            query = query.filter(Document.vision_processed_at.is_(None))

        documents = query.all()

        logger.info(f"Vision sweep for case {case.case_number}: {len(documents)} documents to process")

        for doc in documents:
            if not doc.file_path or not os.path.exists(doc.file_path):
                summary['documents_skipped'] += 1
                summary['errors'].append(f"Doc {doc.id}: file not found")
                continue

            result = extract_structured_data(doc.file_path)

            # Update tracking
            doc.vision_processed_at = datetime.utcnow()

            summary['documents_processed'] += 1
            summary['total_cost_cents'] += result.get('cost_cents', 0)
            summary['results'].append({
                'document_id': doc.id,
                'document_name': doc.document_name,
                **result
            })

            if result.get('error'):
                summary['errors'].append(f"Doc {doc.id}: {result['error']}")

        session.commit()

    logger.info(f"Vision sweep complete: {summary['documents_processed']} docs, ${summary['total_cost_cents']:.2f}")

    return summary


def update_case_from_vision_results(case_id: int, results: list) -> bool:
    """
    Update case record with Vision-extracted data.

    Uses latest document data. Null values don't overwrite existing.
    Property address uses first-set-wins (sticky).

    Args:
        case_id: Database ID of the case
        results: List of extraction results from sweep_case_documents

    Returns:
        True if case was updated
    """
    from database.connection import get_session
    from database.models import Case

    if not results:
        return False

    # Sort by document_id descending (newer documents first)
    sorted_results = sorted(results, key=lambda x: x.get('document_id', 0), reverse=True)

    # Merge results - later values fill in gaps
    merged = {}
    fields = ['property_address', 'legal_description', 'bid_amount',
              'minimum_next_bid', 'deposit_required', 'sale_date',
              'trustee_name', 'attorney_name', 'attorney_phone', 'attorney_email']

    for field in fields:
        for result in sorted_results:
            if result.get(field) is not None:
                merged[field] = result[field]
                break

    if not merged:
        return False

    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            return False

        updated = False

        # Property address: first-set-wins (sticky)
        if 'property_address' in merged and not case.property_address:
            case.property_address = merged['property_address']
            updated = True
            logger.info(f"Case {case.case_number}: Set property_address via Vision")

        # Financial fields: always update if we have new data
        if 'bid_amount' in merged and merged['bid_amount']:
            case.current_bid_amount = merged['bid_amount']
            updated = True

        if 'minimum_next_bid' in merged and merged['minimum_next_bid']:
            case.minimum_next_bid = merged['minimum_next_bid']
            updated = True

        # Other fields: update if currently empty
        if 'legal_description' in merged and not case.legal_description:
            case.legal_description = merged['legal_description']
            updated = True

        if 'sale_date' in merged and not case.sale_date:
            from datetime import datetime
            try:
                case.sale_date = datetime.strptime(merged['sale_date'], '%Y-%m-%d').date()
                updated = True
            except (ValueError, TypeError):
                pass

        if updated:
            session.commit()
            logger.info(f"Case {case.case_number}: Updated from Vision extraction")

        return updated
