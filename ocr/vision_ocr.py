"""Claude Vision OCR for handwritten text extraction.

Uses Claude's vision capabilities to extract structured data from PDF documents
when Tesseract OCR fails to capture handwritten fields.

This is used as a fallback for Report of Sale and Upset Bid documents
where bid amounts are often handwritten.
"""

import base64
import os
from decimal import Decimal
from typing import Dict, Optional, Any
from pathlib import Path

from pdf2image import convert_from_path
from PIL import Image
import io

from common.logger import setup_logger
from common.config import config

logger = setup_logger(__name__)

# Document types that should use vision OCR fallback
VISION_OCR_DOCUMENT_TYPES = [
    'report of foreclosure sale',
    'report of sale',
    'notice of upset bid',
    'upset bid',
]


def _is_vision_ocr_document(document_name: str) -> bool:
    """Check if document type should use vision OCR fallback."""
    if not document_name:
        return False
    name_lower = document_name.lower()
    return any(doc_type in name_lower for doc_type in VISION_OCR_DOCUMENT_TYPES)


def _pdf_to_base64_images(pdf_path: str, max_pages: int = 2) -> list:
    """
    Convert PDF pages to base64-encoded PNG images.

    Args:
        pdf_path: Path to PDF file
        max_pages: Maximum number of pages to convert (default 2)

    Returns:
        List of base64-encoded image strings
    """
    try:
        # Convert PDF to images (200 DPI for good quality)
        images = convert_from_path(pdf_path, dpi=200)

        base64_images = []
        for i, image in enumerate(images[:max_pages]):
            # Convert PIL Image to PNG bytes
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)

            # Encode to base64
            img_base64 = base64.standard_b64encode(buffer.read()).decode('utf-8')
            base64_images.append(img_base64)

        return base64_images

    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        return []


def extract_bid_data_with_vision(pdf_path: str) -> Dict[str, Any]:
    """
    Extract bid data from a PDF using Claude Vision.

    Sends the PDF as an image to Claude and asks it to extract
    specific fields commonly found in NC foreclosure documents.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dict with extracted fields:
        - bid_amount: Decimal or None
        - minimum_next_bid: Decimal or None
        - deposit_required: Decimal or None
        - sale_date: str or None (MM/DD/YYYY format)
        - deadline_date: str or None (MM/DD/YYYY format)
    """
    result = {
        'bid_amount': None,
        'minimum_next_bid': None,
        'deposit_required': None,
        'sale_date': None,
        'deadline_date': None,
    }

    if not config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not configured, skipping vision OCR")
        return result

    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        return result

    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed. Run: pip install anthropic")
        return result

    # Convert PDF to images
    images = _pdf_to_base64_images(pdf_path)
    if not images:
        logger.error(f"Failed to convert PDF to images: {pdf_path}")
        return result

    logger.info(f"  Running Claude Vision OCR on {os.path.basename(pdf_path)}")

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        # Build content with images
        content = []
        for i, img_base64 in enumerate(images):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": img_base64,
                }
            })

        # Add the extraction prompt
        content.append({
            "type": "text",
            "text": """This is a North Carolina court foreclosure document. Please extract the following fields if present.
Return ONLY a JSON object with these exact keys (use null for fields not found):

{
  "bid_amount": "the Amount Bid or highest bid amount as a number without $ or commas",
  "minimum_next_bid": "the Minimum Amount of Next Upset Bid as a number without $ or commas",
  "deposit_required": "the Amount of Deposit Required to Upset Bid as a number without $ or commas",
  "sale_date": "the Date of Sale in MM/DD/YYYY format",
  "deadline_date": "the Last Date For Upset Bid in MM/DD/YYYY format"
}

Important:
- Look carefully for handwritten amounts in the form fields
- The bid amount may be written as "$65,000.00" or "65,000.00" or similar
- Some fields may be blank - return null for those
- Return ONLY the JSON object, no other text"""
        })

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {"role": "user", "content": content}
            ]
        )

        # Parse the response
        response_text = response.content[0].text.strip()
        logger.debug(f"  Vision OCR response: {response_text}")

        # Extract JSON from response
        import json
        import re

        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            # Parse bid_amount
            if data.get('bid_amount'):
                try:
                    # Clean and convert to Decimal
                    amount_str = str(data['bid_amount']).replace(',', '').replace('$', '').strip()
                    result['bid_amount'] = Decimal(amount_str)
                    logger.info(f"    Vision OCR found bid_amount: ${result['bid_amount']}")
                except (ValueError, TypeError) as e:
                    logger.debug(f"    Could not parse bid_amount: {data['bid_amount']}")

            # Parse minimum_next_bid
            if data.get('minimum_next_bid'):
                try:
                    amount_str = str(data['minimum_next_bid']).replace(',', '').replace('$', '').strip()
                    result['minimum_next_bid'] = Decimal(amount_str)
                    logger.info(f"    Vision OCR found minimum_next_bid: ${result['minimum_next_bid']}")
                except (ValueError, TypeError):
                    logger.debug(f"    Could not parse minimum_next_bid: {data['minimum_next_bid']}")

            # Parse deposit_required
            if data.get('deposit_required'):
                try:
                    amount_str = str(data['deposit_required']).replace(',', '').replace('$', '').strip()
                    result['deposit_required'] = Decimal(amount_str)
                    logger.info(f"    Vision OCR found deposit_required: ${result['deposit_required']}")
                except (ValueError, TypeError):
                    logger.debug(f"    Could not parse deposit_required: {data['deposit_required']}")

            # Parse dates (keep as strings for now)
            if data.get('sale_date'):
                result['sale_date'] = data['sale_date']
                logger.info(f"    Vision OCR found sale_date: {result['sale_date']}")

            if data.get('deadline_date'):
                result['deadline_date'] = data['deadline_date']
                logger.info(f"    Vision OCR found deadline_date: {result['deadline_date']}")
        else:
            logger.warning(f"  Could not parse JSON from vision response: {response_text[:200]}")

    except anthropic.APIError as e:
        logger.error(f"  Anthropic API error: {e}")
    except Exception as e:
        logger.error(f"  Vision OCR failed: {e}")

    return result


def should_use_vision_fallback(document_name: str, tesseract_text: str,
                                extracted_bid: Optional[Decimal] = None) -> bool:
    """
    Determine if we should use vision OCR fallback for a document.

    Args:
        document_name: Name of the document
        tesseract_text: Text extracted by Tesseract
        extracted_bid: Bid amount extracted from Tesseract text (if any)

    Returns:
        True if vision fallback should be used
    """
    # Only use for specific document types
    if not _is_vision_ocr_document(document_name):
        return False

    # If we already extracted a bid, no need for fallback
    if extracted_bid is not None:
        return False

    # Check if Tesseract captured any dollar amounts
    # If the text has "Amount Bid" but no dollar figure after it, likely handwritten
    import re
    has_amount_label = bool(re.search(r'Amount\s*(?:of\s+)?Bid', tesseract_text, re.IGNORECASE))
    has_dollar_amount = bool(re.search(r'\$\s*[\d,]+\.?\d*', tesseract_text))

    # Use vision if we see the label but no amount
    if has_amount_label and not has_dollar_amount:
        logger.debug(f"  Document has 'Amount Bid' label but no dollar amount - using vision fallback")
        return True

    # Also use vision if minimum_next_bid fields are empty (clerk didn't fill in)
    has_minimum_label = bool(re.search(r'Minimum\s+Amount.*Next\s+Upset', tesseract_text, re.IGNORECASE))
    has_minimum_value = bool(re.search(r'Minimum\s+Amount.*Next\s+Upset[\s\S]{0,100}\$\s*[\d,]+', tesseract_text, re.IGNORECASE))

    if has_minimum_label and not has_minimum_value:
        logger.debug(f"  Document has 'Minimum Amount' label but no value - using vision fallback")
        return True

    return False
