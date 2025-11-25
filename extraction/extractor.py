"""Pattern-matching data extraction from OCR text.

Extracts structured data from PDF documents using regex patterns.
No LLM required - all data follows predictable formats in NC Court documents.
"""

import re
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, Dict, Any, Tuple

from database.connection import get_session
from database.models import Case, Document
from common.logger import setup_logger

logger = setup_logger(__name__)


# =============================================================================
# REGEX PATTERNS
# =============================================================================

# Property Address patterns
# Format: "ADDRESS/LOCATION OF PROPERTY BEING FORECLOSED:" followed by address
ADDRESS_PATTERNS = [
    # Pattern 1: After "ADDRESS/LOCATION OF PROPERTY" header
    r'ADDRESS/LOCATION\s+OF\s+PROPERTY\s*(?:BEING\s+FORECLOSED)?[:\s]*\n+\s*([^\n]+(?:NC|North\s+Carolina)\s*\d{5}(?:-\d{4})?)',
    # Pattern 2: Multi-line address (street on one line, city/state on next)
    r'ADDRESS/LOCATION\s+OF\s+PROPERTY\s*(?:BEING\s+FORECLOSED)?[:\s]*\n+\s*(\d+[^\n]+)\n+\s*([A-Z][A-Za-z\s]+,\s*NC\s*\d{5})',
    # Pattern 3: "commonly known as"
    r'(?:commonly\s+known\s+as|known\s+as)[:\s]+([^.]+(?:NC|North\s+Carolina)\s*\d{5}(?:-\d{4})?)',
    # Pattern 4: "Property Address:"
    r'Property\s+Address[:\s]+([^\n]+(?:NC|North\s+Carolina)\s*\d{5}(?:-\d{4})?)',
]

# Bid Amount patterns (from Report of Foreclosure Sale)
BID_AMOUNT_PATTERNS = [
    r'Amount\s+Bid[:\s]*\$?\s*([\d,]+\.?\d*)',
    r'AMOUNT\s+BID[:\s]*\$?\s*([\d,]+\.?\d*)',
    r'winning\s+bid[:\s]*\$?\s*([\d,]+\.?\d*)',
]

# Upset Bid Deadline patterns
UPSET_DEADLINE_PATTERNS = [
    r'Last\s+Date\s+(?:For|for)\s+Upset\s+Bid[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
    r'LAST\s+DATE\s+FOR\s+UPSET\s+BID[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
    r'upset\s+bid\s+deadline[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
]

# Sale Date patterns
SALE_DATE_PATTERNS = [
    r'Date\s+Of\s+Sale[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
    r'DATE\s+OF\s+SALE[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
    r'sale\s+(?:was\s+)?held\s+on\s+(\d{1,2}/\d{1,2}/\d{4})',
    # Pattern for written dates like "MARCH 13, 2024"
    r'(?:on|held\s+on)\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
]

# Legal Description patterns
LEGAL_DESCRIPTION_PATTERNS = [
    # Pattern for "Being all of Lot X..."
    r'(Being\s+all\s+of\s+Lot\s+\d+[^.]+(?:Registry|Records)[^.]*\.)',
    # Pattern for lot descriptions
    r'(Lot\s+\d+,?\s+(?:Block\s+\w+,?\s+)?[^,]+(?:Subdivision|Phase)[^.]+\.)',
]

# Trustee Name patterns
TRUSTEE_PATTERNS = [
    r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),?\s+Trustee',
    r'Trustee[:\s]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
]

# Attorney patterns
ATTORNEY_NAME_PATTERNS = [
    r'Bar\s+No\.?\s*(\d+)',
    r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),?\s+(?:Trustee|Attorney)',
]

PHONE_PATTERNS = [
    r'(\d{3}[-.]?\d{3}[-.]?\d{4})',
]

EMAIL_PATTERNS = [
    r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
]


# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================

def extract_property_address(ocr_text: str) -> Optional[str]:
    """
    Extract property address from OCR text.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        Property address string or None if not found
    """
    if not ocr_text:
        return None

    # Try each pattern
    for pattern in ADDRESS_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE | re.MULTILINE)
        if match:
            # Handle multi-group patterns (street + city)
            if len(match.groups()) > 1:
                address = f"{match.group(1).strip()}, {match.group(2).strip()}"
            else:
                address = match.group(1).strip()

            # Clean up extra whitespace
            address = re.sub(r'\s+', ' ', address)
            return address

    return None


def extract_bid_amount(ocr_text: str) -> Optional[Decimal]:
    """
    Extract current bid amount from Report of Foreclosure Sale.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        Bid amount as Decimal or None if not found
    """
    if not ocr_text:
        return None

    for pattern in BID_AMOUNT_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return Decimal(amount_str)
            except:
                continue

    return None


def extract_upset_deadline(ocr_text: str) -> Optional[datetime]:
    """
    Extract upset bid deadline from Report of Foreclosure Sale.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        Deadline as datetime or None if not found
    """
    if not ocr_text:
        return None

    for pattern in UPSET_DEADLINE_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            try:
                return datetime.strptime(date_str, '%m/%d/%Y')
            except ValueError:
                continue

    return None


def extract_sale_date(ocr_text: str) -> Optional[date]:
    """
    Extract foreclosure sale date from documents.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        Sale date or None if not found
    """
    if not ocr_text:
        return None

    for pattern in SALE_DATE_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            # Try different date formats
            for fmt in ['%m/%d/%Y', '%B %d, %Y', '%B %d %Y']:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue

    return None


def extract_legal_description(ocr_text: str) -> Optional[str]:
    """
    Extract legal property description from documents.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        Legal description or None if not found
    """
    if not ocr_text:
        return None

    for pattern in LEGAL_DESCRIPTION_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE | re.DOTALL)
        if match:
            desc = match.group(1).strip()
            # Clean up excessive whitespace but preserve structure
            desc = re.sub(r'\s+', ' ', desc)
            return desc

    return None


def extract_trustee_name(ocr_text: str) -> Optional[str]:
    """
    Extract trustee name from documents.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        Trustee name or None if not found
    """
    if not ocr_text:
        return None

    for pattern in TRUSTEE_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def extract_attorney_info(ocr_text: str) -> Dict[str, Optional[str]]:
    """
    Extract attorney information from documents.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        Dict with 'name', 'phone', 'email' keys
    """
    result = {'name': None, 'phone': None, 'email': None}

    if not ocr_text:
        return result

    # Extract attorney/trustee name
    for pattern in ATTORNEY_NAME_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            # Skip bar numbers, get names
            if not match.group(1).isdigit():
                result['name'] = match.group(1).strip()
                break

    # Extract phone
    phones = re.findall(PHONE_PATTERNS[0], ocr_text)
    if phones:
        # Take the first phone number that looks like a business number
        result['phone'] = phones[0]

    # Extract email
    emails = re.findall(EMAIL_PATTERNS[0], ocr_text)
    if emails:
        result['email'] = emails[0].lower()

    return result


def extract_from_document(ocr_text: str) -> Dict[str, Any]:
    """
    Extract all available data from a single document's OCR text.

    Args:
        ocr_text: Raw OCR text

    Returns:
        Dict with all extracted fields
    """
    attorney_info = extract_attorney_info(ocr_text)

    return {
        'property_address': extract_property_address(ocr_text),
        'current_bid_amount': extract_bid_amount(ocr_text),
        'next_bid_deadline': extract_upset_deadline(ocr_text),
        'sale_date': extract_sale_date(ocr_text),
        'legal_description': extract_legal_description(ocr_text),
        'trustee_name': extract_trustee_name(ocr_text),
        'attorney_name': attorney_info.get('name'),
        'attorney_phone': attorney_info.get('phone'),
        'attorney_email': attorney_info.get('email'),
    }


def extract_all_from_case(case_id: int) -> Dict[str, Any]:
    """
    Extract all available data from all documents for a case.

    Combines data from all documents, preferring non-null values.

    Args:
        case_id: Database ID of the case

    Returns:
        Dict with all extracted fields (best values from all documents)
    """
    result = {
        'property_address': None,
        'current_bid_amount': None,
        'next_bid_deadline': None,
        'sale_date': None,
        'legal_description': None,
        'trustee_name': None,
        'attorney_name': None,
        'attorney_phone': None,
        'attorney_email': None,
    }

    with get_session() as session:
        documents = session.query(Document).filter_by(case_id=case_id).all()

        for doc in documents:
            if not doc.ocr_text:
                continue

            doc_data = extract_from_document(doc.ocr_text)

            # Merge data, preferring non-null values
            for key, value in doc_data.items():
                if value is not None and result[key] is None:
                    result[key] = value

    return result


def update_case_with_extracted_data(case_id: int) -> bool:
    """
    Extract data from case documents and update the case record.

    Args:
        case_id: Database ID of the case

    Returns:
        True if case was updated, False otherwise
    """
    try:
        extracted = extract_all_from_case(case_id)

        # Check if we have any data to update
        has_data = any(v is not None for v in extracted.values())
        if not has_data:
            logger.debug(f"  No data extracted for case {case_id}")
            return False

        with get_session() as session:
            case = session.query(Case).filter_by(id=case_id).first()
            if not case:
                logger.warning(f"  Case {case_id} not found")
                return False

            # Update fields only if we have new data and field is empty
            updated_fields = []

            if extracted['property_address'] and not case.property_address:
                case.property_address = extracted['property_address']
                updated_fields.append('property_address')

            if extracted['current_bid_amount'] and not case.current_bid_amount:
                case.current_bid_amount = extracted['current_bid_amount']
                updated_fields.append('current_bid_amount')

            if extracted['next_bid_deadline'] and not case.next_bid_deadline:
                case.next_bid_deadline = extracted['next_bid_deadline']
                updated_fields.append('next_bid_deadline')

            if extracted['sale_date'] and not case.sale_date:
                case.sale_date = extracted['sale_date']
                updated_fields.append('sale_date')

            if extracted['legal_description'] and not case.legal_description:
                case.legal_description = extracted['legal_description']
                updated_fields.append('legal_description')

            if extracted['trustee_name'] and not case.trustee_name:
                case.trustee_name = extracted['trustee_name']
                updated_fields.append('trustee_name')

            if extracted['attorney_name'] and not case.attorney_name:
                case.attorney_name = extracted['attorney_name']
                updated_fields.append('attorney_name')

            if extracted['attorney_phone'] and not case.attorney_phone:
                case.attorney_phone = extracted['attorney_phone']
                updated_fields.append('attorney_phone')

            if extracted['attorney_email'] and not case.attorney_email:
                case.attorney_email = extracted['attorney_email']
                updated_fields.append('attorney_email')

            if updated_fields:
                session.commit()
                logger.info(f"  Updated case {case_id}: {', '.join(updated_fields)}")
                return True
            else:
                logger.debug(f"  No new data for case {case_id}")
                return False

    except Exception as e:
        logger.error(f"  Error extracting data for case {case_id}: {e}")
        return False


def process_unextracted_cases(limit: int = None) -> int:
    """
    Process all cases that have OCR text but missing extracted fields.

    Args:
        limit: Maximum number of cases to process (None for all)

    Returns:
        Number of cases updated
    """
    with get_session() as session:
        # Find cases with documents that have OCR text but case is missing key fields
        query = session.query(Case).join(Document).filter(
            Document.ocr_text.isnot(None),
            Case.property_address.is_(None)  # Proxy for "not yet extracted"
        ).distinct()

        if limit:
            query = query.limit(limit)

        cases = query.all()
        logger.info(f"Found {len(cases)} cases to process")

    updated_count = 0
    for case in cases:
        if update_case_with_extracted_data(case.id):
            updated_count += 1

    return updated_count
