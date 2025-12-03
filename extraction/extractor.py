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

# =============================================================================
# AOC-SP-403 (Notice of Upset Bid) PATTERNS - NC Standard Form
# =============================================================================
# NOTE: These patterns need to handle OCR artifacts including:
# - Extra spaces inside numbers ("45, 000.00" instead of "45,000.00")
# - Typos ("UpsetBd" instead of "UpsetBid")
# - Variable whitespace between fields
# - Dollar signs may have extra spaces ("$   47,256.00")

# Helper: Match dollar amount with potential spaces inside numbers
# Matches: $47,256.00 or $ 47,256.00 or 47, 256.00 etc.
# Captures the whole number portion which we'll clean up later
# Also handles line breaks between label and amount (common in PDF extraction)
DOLLAR_AMOUNT = r'[\$\']?\s*(\d[\d,\.\s]+\d{2})'

# Current upset bid amount - the new higher bid being filed
# NOTE: In PDF forms, the label and value may be on separate lines, so we
# capture based on position relative to other fields
UPSET_BID_NEW_AMOUNT_PATTERNS = [
    # "AmountofNew UpsetBd" followed later by $47,256.00
    # Use multiline pattern with [\s\S] to match across lines
    r'AmountofNew\s*Upset\s*B[id]*[\s\S]{1,100}?' + DOLLAR_AMOUNT,
    r'Amount\s*[Oo]f\s*New\s*Upset\s*B[id]*[\s\S]{1,100}?' + DOLLAR_AMOUNT,
    # Direct dollar pattern when next to label
    r'New\s*Upset\s*B[id]*\s*' + DOLLAR_AMOUNT,
]

# Previous bid amount - the bid being upset
UPSET_BID_PREVIOUS_AMOUNT_PATTERNS = [
    # "Amount Of Last Previous Sale Or Upset Bid" followed by '$45,000.00'
    # The label is on one line, value on the next in PDF forms
    r'Amount\s*[Oo]f\s*Last\s*Previous\s*(?:Sale|Upset)[\s\S]{1,100}?' + DOLLAR_AMOUNT,
    r'Last\s*Previous\s*Sale\s*(?:[Oo]r)?\s*Upset[\s\S]{1,100}?' + DOLLAR_AMOUNT,
    # Direct capture near "Previous Sale" text
    r'Previous\s*(?:Sale|Bid)[\s\S]{1,50}?' + DOLLAR_AMOUNT,
]

# Minimum next upset bid amount - key for bidding strategy
MINIMUM_NEXT_UPSET_PATTERNS = [
    # "*Minimum Am junt Of Next Upset! Bat" (with OCR typos) followed by $49,612.50
    # Handle OCR typos: "Am junt" = "Amount", "Bat" = "Bid"
    r'[*\"]?[Mm]inimum\s*[Aa]m[ou\s]*[nrt]*\s*(?:[Oo]f)?\s*[Nn]ext\s*[Uu]pset[!\s]*[Bb][adit]*[\s\S]{1,100}?' + DOLLAR_AMOUNT,
    r'Next\s*(?:Minimum)?\s*Upset\s*B[id]*[\s\S]{1,50}?' + DOLLAR_AMOUNT,
]

# Deposit required for next upset bid
UPSET_DEPOSIT_PATTERNS = [
    # "Amount of Deposit For Next Minimum Upset Bid" followed by $2,480.63
    r'Deposit\s*(?:[Ff]or)?\s*[Nn]ext\s*(?:Minimum)?\s*Upset[\s\S]{1,100}?' + DOLLAR_AMOUNT,
    r'Amount\s*(?:[Oo]f)?\s*Deposit[\s\S]{1,80}?[Nn]ext[\s\S]{1,50}?' + DOLLAR_AMOUNT,
]

# Upset Bid Deadline patterns (enhanced)
UPSET_DEADLINE_PATTERNS = [
    # From AOC-SP-403: "Last Day For Nex! Upset" (note: OCR may render 't' as '!')
    # followed by 12/4/2025 on next line
    r'Last\s*Day\s*(?:[Ff]or)?\s*[Nn]ex[ti!]\s*[Uu]pset[\s\S]{1,50}?(\d{1,2}/\d{1,2}/\d{4})',
    r'Last\s+Date\s+(?:[Ff]or)\s+Upset\s+Bid[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
    r'LAST\s+DATE\s+FOR\s+UPSET\s+BID[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
    r'upset\s+bid\s+deadline[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
    # "Next Upset" followed by date
    r'[Nn]ext\s*[Uu]pset[\s\S]{1,30}?(\d{1,2}/\d{1,2}/\d{4})',
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


# =============================================================================
# AOC-SP-403 (Notice of Upset Bid) EXTRACTION FUNCTIONS
# =============================================================================

def extract_upset_bid_data(ocr_text: str) -> Dict[str, Any]:
    """
    Extract all data from an AOC-SP-403 (Notice of Upset Bid) form.

    This NC standard form contains crucial bid information:
    - Current upset bid amount (the new bid being filed)
    - Previous bid amount (the bid being upset)
    - Minimum next upset bid (for bidding strategy)
    - Next upset bid deadline
    - Required deposit amount

    Args:
        ocr_text: Raw OCR text from upset bid document

    Returns:
        Dict with keys: current_bid, previous_bid, minimum_next_bid,
                       next_deadline, deposit_required
    """
    result = {
        'current_bid': None,
        'previous_bid': None,
        'minimum_next_bid': None,
        'next_deadline': None,
        'deposit_required': None,
    }

    if not ocr_text:
        return result

    def clean_amount(amount_str: str) -> Optional[Decimal]:
        """Clean OCR amount string and convert to Decimal.

        Handles OCR artifacts like:
        - Extra spaces: "45, 000.00" -> "45000.00"
        - Various delimiters: "47,256.00" -> "47256.00"
        """
        if not amount_str:
            return None
        # Remove all whitespace, commas, and normalize
        cleaned = ''.join(c for c in amount_str if c.isdigit() or c == '.')
        # Validate it looks like a reasonable amount
        if cleaned and '.' in cleaned:
            try:
                amount = Decimal(cleaned)
                # Filter out unreasonable values (less than $100 or more than $100M)
                if 100 <= amount <= 100000000:
                    return amount
            except:
                pass
        return None

    # Find all dollar amounts in the document with their positions
    # This helps with documents where labels and values are in columns
    dollar_pattern = r'[\$\']?\s*(\d[\d,\.\s]+\.\d{2})'
    all_amounts = []
    for m in re.finditer(dollar_pattern, ocr_text):
        amount = clean_amount(m.group(1))
        if amount:
            all_amounts.append((m.start(), amount, m.group(0)))

    # For AOC-SP-403 forms, the amounts typically appear in this order:
    # 1. Previous bid (Amount Of Last Previous Sale Or Upset Bid)
    # 2. New upset bid (AmountofNew UpsetBd)
    # 3. Deposit amount (past With Clerk)
    # 4. Minimum next bid (at the bottom of the form)
    # 5. Deposit for next upset

    # Use pattern matching to find the approximate location of each label
    # then assign the nearest amount

    # Check if this is an AOC-SP-403 style form
    is_aoc_sp_403 = ('AmountofNew' in ocr_text or
                     'Amount Of New' in ocr_text.replace('  ', ' ') or
                     'NOTICE OF UPSET BID' in ocr_text.upper())

    if is_aoc_sp_403:
        # AOC-SP-403 forms have TWO sections:
        # 1. TOP section (handwritten/fillable): Previous bid, New upset bid, Deposit with clerk
        # 2. BOTTOM section (typed by clerk): Last Day, Minimum NEXT upset, Deposit for NEXT upset
        #
        # The BOTTOM section is most reliable since it's typed. Key insight:
        # - "Minimum Amount Of Next Upset Bid" = current_bid * 1.05
        # - So current_bid = minimum_next_bid / 1.05

        # First, try to extract the reliable BOTTOM section values
        # The bottom section has labels on one line and values on the next:
        # Line 1: "Last Day For Next Upset Bid    M nimum Amount Of Next Upset Bid    Amount Of Deposit..."
        # Line 2: "12/11/2025                     $58,782.80                          $2,939.14"
        #
        # Strategy: Find the label, then find the first dollar amount AFTER it
        # (may be separated by many characters including newlines)

        # Look for "M nimum Amount Of Next Upset Bid" or similar (handles OCR typos)
        min_next_match = re.search(
            r'[Mm][\s]*[in]*[i]*mum\s*[Aa]mount\s*[Oo]f\s*[Nn]ext\s*[Uu]pset\s*[Bb]id',
            ocr_text, re.IGNORECASE
        )
        if min_next_match:
            # Look for a dollar amount after this label
            # The amount should be within 200 chars (allows for spacing and next label)
            after_label = ocr_text[min_next_match.end():min_next_match.end()+200]
            amt_match = re.search(r'\$?\s*(\d[\d,\.\s]+\.\d{2})', after_label)
            if amt_match:
                min_amt = clean_amount(amt_match.group(1))
                if min_amt:
                    result['minimum_next_bid'] = min_amt
                    # Calculate current bid as minimum / 1.05
                    result['current_bid'] = round(min_amt / Decimal('1.05'), 2)

        # Look for deposit for next upset
        # In columnar layout, all 3 labels are on one line and all 3 values on the next
        # So "Amount Of Deposit For Next Minimum Upset Bid" is followed by ALL three values
        # We need the LAST value (rightmost in the row) which is the deposit
        deposit_next_match = re.search(
            r'[Aa]mount\s*[Oo]f\s*[Dd]eposit\s*[Ff]or\s*[Nn]ext',
            ocr_text, re.IGNORECASE
        )
        if deposit_next_match:
            # Look for ALL dollar amounts after this label (within next line)
            after_label = ocr_text[deposit_next_match.end():deposit_next_match.end()+200]
            amt_matches = list(re.finditer(r'\$?\s*(\d[\d,\.\s]+\.\d{2})', after_label))
            # The deposit is the LAST (rightmost) amount in the columnar row
            if amt_matches:
                deposit_amt = clean_amount(amt_matches[-1].group(1))
                if deposit_amt:
                    result['deposit_required'] = deposit_amt

        # If bottom section extraction succeeded, we have the current bid
        # Now try to get previous bid from TOP section if available
        if result['current_bid']:
            # Look for "Amount Of Last Previous Sale Or Upset Bid" in TOP section
            # This is before the "Amount Of New Upset Bid" label
            prev_match = re.search(
                r'Last\s*Previous\s*Sale\s*[Oo]r\s*Upset\s*Bid[\s\S]{0,100}?\$?\s*(\d[\d,\.\s]+\.\d{2})',
                ocr_text, re.IGNORECASE
            )
            if prev_match:
                prev_amt = clean_amount(prev_match.group(1))
                if prev_amt and prev_amt < result['current_bid']:
                    result['previous_bid'] = prev_amt

        # Fallback: if we didn't get current_bid from bottom section, try position-based
        if not result['current_bid']:
            # Find position markers
            prev_pos = -1
            new_pos = -1
            min_pos = -1
            deposit_pos = -1

            m = re.search(r'Last\s*Previous\s*Sale', ocr_text, re.IGNORECASE)
            if m:
                prev_pos = m.end()

            m = re.search(r'AmountofNew|Amount\s*[Oo]f\s*New', ocr_text, re.IGNORECASE)
            if m:
                new_pos = m.end()

            m = re.search(r'[Mm]inimum\s*Am|Next\s*Upset[!\s]*B', ocr_text, re.IGNORECASE)
            if m:
                min_pos = m.end()

            m = re.search(r'Deposit\s*(?:For|for)?\s*Next', ocr_text, re.IGNORECASE)
            if m:
                deposit_pos = m.end()

            # Assign amounts based on position
            # For columnar forms, amounts appear on the line AFTER the labels
            if all_amounts and prev_pos >= 0:
                # Find amounts after the previous label position
                candidates = [(pos, amt) for pos, amt, _ in all_amounts if pos > prev_pos]
                if candidates:
                    # First amount after "Previous Sale" label is likely the previous bid
                    result['previous_bid'] = candidates[0][1]
                    # Second amount is likely the new bid (in the adjacent column)
                    if len(candidates) > 1:
                        result['current_bid'] = candidates[1][1]

            # Minimum and deposit are usually at the bottom
            if min_pos >= 0 and all_amounts:
                candidates = [(pos, amt) for pos, amt, _ in all_amounts if pos > min_pos]
                if candidates:
                    result['minimum_next_bid'] = candidates[0][1]
                    if len(candidates) > 1:
                        result['deposit_required'] = candidates[1][1]

    else:
        # Fall back to pattern-based extraction for non-columnar documents
        for pattern in UPSET_BID_NEW_AMOUNT_PATTERNS:
            match = re.search(pattern, ocr_text, re.IGNORECASE | re.DOTALL)
            if match:
                amount = clean_amount(match.group(1))
                if amount:
                    result['current_bid'] = amount
                    break

        for pattern in UPSET_BID_PREVIOUS_AMOUNT_PATTERNS:
            match = re.search(pattern, ocr_text, re.IGNORECASE | re.DOTALL)
            if match:
                amount = clean_amount(match.group(1))
                if amount:
                    result['previous_bid'] = amount
                    break

        for pattern in MINIMUM_NEXT_UPSET_PATTERNS:
            match = re.search(pattern, ocr_text, re.IGNORECASE | re.DOTALL)
            if match:
                amount = clean_amount(match.group(1))
                if amount:
                    result['minimum_next_bid'] = amount
                    break

        for pattern in UPSET_DEPOSIT_PATTERNS:
            match = re.search(pattern, ocr_text, re.IGNORECASE | re.DOTALL)
            if match:
                amount = clean_amount(match.group(1))
                if amount:
                    result['deposit_required'] = amount
                    break

    # Extract next upset deadline - use position-based for columnar forms
    # In AOC-SP-403, the "Last Day For Next Upset" label may be on a different line
    # than the date, so we look for dates near the deadline label position
    if 'AmountofNew' in ocr_text or 'Amount Of New' in ocr_text.replace('  ', ' '):
        # This is a columnar AOC-SP-403 form - use position-based extraction
        # Find the "Last Day For Nex! Upset" label (OCR may render 't' as '!')
        deadline_label_match = re.search(
            r'Last\s*Day\s*(?:[Ff]or)?\s*[Nn]ex[ti!]\s*[Uu]pset',
            ocr_text, re.IGNORECASE
        )

        if deadline_label_match:
            deadline_label_pos = deadline_label_match.end()

            # Find all dates in the document
            date_pattern = r'(\d{1,2}/\d{1,2}/\d{4})'
            all_dates = [(m.start(), m.group(1)) for m in re.finditer(date_pattern, ocr_text)]

            # Find the closest date after the deadline label
            # In columnar layout, dates appear after labels on the same or next line
            candidates = [(pos, d) for pos, d in all_dates if pos > deadline_label_pos]
            if candidates:
                # First date after "Last Day For Next Upset" is the deadline
                try:
                    result['next_deadline'] = datetime.strptime(candidates[0][1], '%m/%d/%Y')
                except ValueError:
                    pass

    # Fall back to pattern-based extraction if position-based didn't find it
    if result['next_deadline'] is None:
        result['next_deadline'] = extract_upset_deadline(ocr_text)

    return result


def is_upset_bid_document(ocr_text: str) -> bool:
    """
    Check if the document is an AOC-SP-403 (Notice of Upset Bid) form.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        True if this appears to be an upset bid notice
    """
    if not ocr_text:
        return False

    # Look for form identifier or key phrases
    indicators = [
        'NOTICE OF UPSET BID',
        'AOC-SP-403',
        'Amount Of New Upset Bid',
        'AmountofNew UpsetBid',
        'Last Day For Next Upset',
        'Minimum Am.*?Next Upset',
    ]

    text_lower = ocr_text.lower()
    for indicator in indicators:
        if re.search(indicator, ocr_text, re.IGNORECASE):
            return True

    return False


def is_report_of_sale_document(ocr_text: str) -> bool:
    """
    Check if the document is a Report of Foreclosure Sale.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        True if this appears to be a report of sale
    """
    if not ocr_text:
        return False

    indicators = [
        'REPORT OF.*FORECLOSURE SALE',
        'Report of Sale',
        'Report of Foreclosure Sale',
        'AOC-SP-',  # Other AOC forms related to sales
        'Date Of Sale',
        'Amount Bid',
    ]

    for indicator in indicators:
        if re.search(indicator, ocr_text, re.IGNORECASE):
            return True

    return False


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
                # NC law: minimum next bid is 5% higher than current bid
                case.minimum_next_bid = round(extracted['current_bid_amount'] * Decimal('1.05'), 2)
                updated_fields.append('current_bid_amount')
                updated_fields.append('minimum_next_bid')

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
