"""Pattern-matching data extraction from OCR text.

Extracts structured data from PDF documents using regex patterns.
No LLM required - all data follows predictable formats in NC Court documents.
"""

import os
import re
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, Dict, Any, Tuple, List

from datetime import timedelta
from database.connection import get_session
from database.models import Case, Document, CaseEvent
from common.logger import setup_logger
from common.business_days import calculate_upset_bid_deadline

logger = setup_logger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def clean_amount(amount_str: str) -> Optional[Decimal]:
    """
    Clean a dollar amount string and convert to Decimal.

    Args:
        amount_str: String containing a dollar amount (e.g., "856,161.56", "$9,830.00")

    Returns:
        Decimal amount or None if invalid
    """
    if not amount_str:
        return None
    try:
        # Remove $ and spaces first
        cleaned = amount_str.replace('$', '').replace(' ', '').strip()

        # Detect malformed European-style amounts like "350,00.00" (should be "350,000.00")
        # Pattern: 1-3 digits, comma, exactly 2 digits, period, exactly 2 digits
        # This is likely a typo where someone meant to type "XXX,XXX.XX" but typed "XXX,XX.XX"
        malformed_pattern = re.match(r'^(\d{1,3}),(\d{2})\.(\d{2})$', cleaned)
        if malformed_pattern:
            # Likely meant to have 3 digits after comma - add a zero
            corrected = f"{malformed_pattern.group(1)},{malformed_pattern.group(2)}0.{malformed_pattern.group(3)}"
            logger.warning(f"  Detected malformed amount '{amount_str}' - correcting to '{corrected}' (assumed missing digit)")
            cleaned = corrected

        # Remove commas and convert
        cleaned = cleaned.replace(',', '')
        return Decimal(cleaned)
    except Exception:
        return None


# =============================================================================
# REGEX PATTERNS
# =============================================================================

# Property Address patterns
# Format: Ordered by priority - EXPLICIT property labels first, generic patterns last
ADDRESS_PATTERNS = [
    # HIGHEST PRIORITY: Explicit property address labels
    # Pattern 1: "The address for the real property is:"
    (r'The\s+address\s+for\s+the\s+real\s+property\s+is[:\s]*\n?\s*([0-9]+[^,\n]+),?\s*\n?\s*([A-Za-z\s]+,\s*(?:NC|North\s+Carolina)\s*\d{5})', 'real_property'),
    # Pattern 2: "Property Address (to post):"
    (r'Property\s+Address\s*\(to\s+post\)[:\s]*\n?\s*([0-9]+[^,\n]+),?\s*\n?\s*([A-Za-z\s]+,\s*(?:NC|North\s+Carolina)\s*\d{5})', 'property_to_post'),
    # Pattern 3: "real property located at"
    (r'real\s+property\s+located\s+at[:\s]+([0-9]+[^,]+,\s*[A-Za-z\s]+,\s*(?:NC|North\s+Carolina)\s*\d{5})', 'located_at'),
    # Pattern 4: "property secured by" (from mortgage documents)
    (r'property\s+secured\s+by[:\s]+([0-9]+[^,]+,\s*[A-Za-z\s]+,\s*(?:NC|North\s+Carolina)\s*\d{5})', 'secured_by'),
    # Pattern 4b: "for real property described as" (Report of Private Sale / estate sales)
    (r'for\s+real\s+property\s+described\s+as\s+([0-9]+[^,\n]+,\s*[A-Za-z\s]+,?\s*(?:NC|North\s+Carolina)\s*\d{5})', 'real_property_described'),

    # HIGH PRIORITY: Standard foreclosure document headers
    # Pattern 5: After "ADDRESS/LOCATION OF PROPERTY" header
    (r'ADDRESS/LOCATION\s+OF\s+PROPERTY\s*(?:BEING\s+FORECLOSED)?[:\s]*\n+\s*([^\n]+(?:NC|North\s+Carolina)\s*\d{5}(?:-\d{4})?)', 'address_location_header'),
    # Pattern 6: Multi-line address (street on one line, city/state on next)
    (r'ADDRESS/LOCATION\s+OF\s+PROPERTY\s*(?:BEING\s+FORECLOSED)?[:\s]*\n+\s*(\d+[^\n]+)\n+\s*([A-Z][A-Za-z\s]+,\s*NC\s*\d{5})', 'address_location_multiline'),
    # Pattern 7: "Address of property:" (different word order - COMMON in NC docs)
    # Use non-greedy match and limit street address capture to 60 chars to avoid capturing legal text
    (r'Address\s+of\s+Property[:\s]+(\d+[^,\n]{1,60},\s*[A-Za-z\s]+,\s*(?:NC|North\s+Carolina)\s*\d{5}(?:-\d{4})?)', 'address_of_property'),
    # Pattern 8: Multi-line after "Address of property:"
    # Stop at street type to avoid capturing text from adjacent columns in two-column OCR layouts
    # (e.g., "5505 Lake Garden Court                       Credit Union" from two-column Notice of Sale)
    (r'Address\s+of\s+Property[:\s]+\n*\s*(\d+[^\n]{1,50}?(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter|Trail|Trl))\s*\n+\s*([A-Z][A-Za-z\s]+,\s*NC\s*\d{5})', 'address_of_property_multiline'),

    # MEDIUM PRIORITY: Common property description patterns
    # Pattern 9: "commonly known as" or "known as"
    (r'(?:commonly\s+known\s+as|known\s+as)[:\s]+([^.]+(?:NC|North\s+Carolina)\s*\d{5}(?:-\d{4})?)', 'commonly_known'),
    # Pattern 10: "Property Address:"
    (r'Property\s+Address[:\s]+([^\n]+(?:NC|North\s+Carolina)\s*\d{5}(?:-\d{4})?)', 'property_address'),
    # Pattern 11: "known as" with street number start (more specific)
    (r'known\s+as\s+(\d+[^,\n]+,\s*[A-Z][A-Za-z\s]+,\s*NC\s*\d{5}(?:-\d{4})?)', 'known_as_specific'),
    # Pattern 12: "assessments upon ADDRESS" (HOA lien foreclosures)
    (r'assessments?\s+upon\s+(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter)[,\s]+[A-Z][A-Za-z\s]+,?\s*NC,?\s*\d{5})', 'assessments_upon'),
    # Pattern 13: "lien upon ADDRESS" (alternative lien foreclosure format)
    (r'lien\s+upon\s+(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter)[,\s]+[A-Z][A-Za-z\s]+,?\s*NC,?\s*\d{5})', 'lien_upon'),

    # LOW PRIORITY: Natural language patterns (affidavits, comma-optional formats)
    # Pattern 14: Affidavit-style natural language "account for [name] at [address]"
    (r'(?:account\s+for\s+[^.]+\s+at|familiar\s+with[^.]+\s+at)\s+(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:NC|North\s+Carolina)\s+\d{5}(?:-\d{4})?)', 'affidavit_at'),
    # Pattern 15: Comma-optional with "North Carolina" spelled out
    (r'(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter))[,.\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+North\s+Carolina\s+\d{5}(?:-\d{4})?)', 'north_carolina_spelled'),
    # Pattern 16: More flexible comma-optional with NC abbreviation
    (r'(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+NC\s+\d{5}(?:-\d{4})?)', 'flexible_nc'),

    # LOWEST PRIORITY: Generic street address pattern (use only as fallback)
    # Pattern 17: Street address followed by City, NC ZIP on same/next line
    (r'(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*\s+(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter)[,.]?)\s*[,\n]\s*([A-Z][A-Za-z\s]+,\s*NC\s*\d{5})', 'generic_street'),
]

# Address Rejection Contexts
# These patterns indicate an address is NOT a property address (attorney/defendant/heir addresses)
REJECT_ADDRESS_CONTEXTS = [
    # OCR-tolerant patterns (allow common OCR errors like "Attormey", "Adgress")
    r'Name\s+And\s+Ad[dg]?ress\s+Of\s+(?:Att?or[mn]ey|Agent|Upset\s+Bidder)',
    r'Att?or[mn]ey\s+[Oo]r\s+Agent\s+[Ff]or\s+Upset\s+Bidder',
    r'For\s+Upset\s+Bidder',  # Simpler catch-all
    r'Upset\s+Bidder\s*\n',  # Header for upset bidder section
    r'Heir\s+of\s+',
    r'TO:\s*\n',
    r'Current\s+Resident',
    r'DEFENDANT[:\s]',
    r'defendant[:\s]',
    r'Unknown\s+Heirs',
    r'Unknown\s+Spouse',
    r'or\s+to\s+the\s+heirs',
    r'service\s+of\s+process',
    r'last\s+known\s+address',
    # Mailing/Correspondence headers (prevent extracting service addresses)
    r'VIA\s+(?:FIRST\s+CLASS|CERTIFIED)\s+MAIL',
    r'CERTIFIED\s+MAIL',
    r'MAIL\s+RETURN\s+RECEIPT',
    r'Attn:',  # "Attention:" in mailing headers
    r'RE:\s*(?:Promissory|Note|Loan|Account)',  # "RE:" in legal correspondence
    # Legal document keywords (indicate legal descriptions, not property addresses)
    r'[Gg]rantor',
    r'[Gg]rantee',
    r'[Tt]rustee',
    r'[Aa]ttorney',
    r'married\s+(?:man|woman)',
    r'sole\s+and\s+separate',
]

# Attorney/Law Firm Address Indicators
# These strings indicate an address is likely a law firm/attorney address, NOT a property
ATTORNEY_ADDRESS_INDICATORS = [
    'Brock & Scott',
    'Brock &: Scott',  # OCR artifact
    'PLLC',
    'P.L.L.C.',
    'Law Firm',
    'Law Office',
    'Attorney',
    'Attorneys at Law',
    'Substitute Trustee',
    'Trustee Services',
]

# Form Artifacts to Filter
# These strings indicate the address contains form field text and should be rejected
FORM_ARTIFACTS = [
    'summons submitted',
    'yes no',
    'yes  no',  # Extra space variant
]

# Document Priority for Address Extraction
# When searching multiple documents for property address, try these types first
# Keywords matched against file_path (case-insensitive)
# IMPORTANT: More specific patterns must come BEFORE generic ones to avoid false matches
# e.g., "notice of sale" must come before "sale" since both match sale documents
ADDRESS_DOCUMENT_PRIORITY = [
    # Highest priority - Notice of Sale/Resale documents contain explicit "Address of Property:" labels
    'notice of saleresale',  # Common combined filename
    'notice of sale',
    'amended notice',
    # Report documents (may or may not have address)
    'report of foreclosure sale',
    'report of sale',
    # Initial filings
    'special proceeding',
    'notice of hearing',
    # Service documents often list property address for posting
    'affidavit of service',
    'return of service',
    # Other affidavits
    'affidavit',
    # Generic foreclosure match (lower priority to avoid matching Report of Foreclosure Sale)
    'foreclosure',
    # Any other document (lowest priority)
]

# Bid Amount patterns (from Report of Foreclosure Sale)
BID_AMOUNT_PATTERNS = [
    r'Amount\s+Bid[:\s]*\$?\s*([\d,]+\.?\d*)',
    r'AMOUNT\s+BID[:\s]*\$?\s*([\d,]+\.?\d*)',
    r'winning\s+bid[:\s]*\$?\s*([\d,]+\.?\d*)',
]

# =============================================================================
# AOC-SP-301 (Report of Foreclosure Sale) PATTERNS - NC Standard Form
# =============================================================================
# The Report of Sale is filed after the auction and contains:
# - The winning bid amount from the auction (this is the FIRST bid)
# - Date of sale (for calculating the 10-day upset period deadline)
# - This form starts the upset bid period

# Report of Sale bid amount patterns
REPORT_OF_SALE_BID_PATTERNS = [
    # Field 5: "Highest Bid Amount" in AOC-SP-301
    r'[Hh]ighest\s*[Bb]id\s*[Aa]mount[\s:]*\$?\s*([\d,]+\.?\d*)',
    # "Amount Bid" or "Amount of Bid" field with multiline gap (common in AOC forms)
    # Also handle OCR errors: Bx, Bld, B1d instead of Bid
    r'[Aa]mount\s+(?:of\s+)?[Bb][il1dx]{1,2}[\s\S]{0,150}?\$([\d,]+\.?\d*)',
    # Alternative wording
    r'[Aa]mount\s*[Oo]f\s*[Ss]uccessful\s*[Bb]id[\s:]*\$?\s*([\d,]+\.?\d*)',
    r'[Pp]roperty\s*(?:was\s+)?[Ss]old\s*[Ff]or[\s:]*\$?\s*([\d,]+\.?\d*)',
    r'[Ww]inning\s*[Bb]id[\s:]*\$?\s*([\d,]+\.?\d*)',
    # Field with OCR artifacts - "Highest Bid" followed by amount on next line
    r'[Hh]ighest\s*[Bb]id[\s\S]{1,50}?\$?\s*(\d[\d,\.\s]+\.\d{2})',
    # Partition sale format: "for the sum of $X"
    r'for\s+the\s+sum\s+of\s*\$\s*([\d,]+\.?\d*)',
    # Report of Private Sale (estate sales): "property was sold on [date], for $X"
    # Allow up to 30 chars between "sold" and "for" to capture the date
    r'(?:property\s+was\s+)?sold\s+(?:on\s+)?[^$]{0,30}?,\s*for\s*\$\s*([\d,]+\.\d{2})',
    # Generic "sold for $X" pattern (immediate adjacency)
    r'sold\s+for\s*\$\s*([\d,]+\.?\d*)',
    # Offer to purchase format (limit search to 50 chars to avoid matching minimum_next_bid)
    r'offer\s+to\s+purchase[^$]{0,50}\$\s*([\d,]+\.?\d*)',
    # Report of Private Sale (estate sales): "The total purchase price is $X"
    r'[Tt]he\s+total\s+purchase\s+price\s+is\s*\$\s*([\d,]+\.?\d*)',
]

# Date of sale patterns for Report of Sale
REPORT_OF_SALE_DATE_PATTERNS = [
    # Field 3: "Date of Sale" in AOC-SP-301
    r'[Dd]ate\s*[Oo]f\s*[Ss]ale[\s:]*(\d{1,2}/\d{1,2}/\d{4})',
    r'[Ss]ale\s*(?:was\s*)?[Hh]eld\s*[Oo]n[\s:]*(\d{1,2}/\d{1,2}/\d{4})',
    r'[Ss]ale\s*[Dd]ate[\s:]*(\d{1,2}/\d{1,2}/\d{4})',
    # Written date format: "sold on January 6, 2026" (common in private sales)
    r'sold\s+on\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})',
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
    # Handle OCR typos: "Am junt" = "Amount", "Bat" = "Bid", "Upsat" = "Upset"
    r'[*\"]?[Mm]inimum\s*[Aa]m[ou\s]*[nrt]*\s*(?:[Oo]f)?\s*[Nn]ext\s*[Uu]ps[ae]t[!\s]*[Bb][adit]*[\s\S]{1,100}?' + DOLLAR_AMOUNT,
    r'Next\s*(?:Minimum)?\s*[Uu]ps[ae]t\s*B[id]*[\s\S]{1,50}?' + DOLLAR_AMOUNT,
    # Report of Private Sale (estate sales): "Next upset bid amount: $X"
    r'[Nn]ext\s+upset\s+bid\s+amount[:\s]*\$\s*([\d,]+\.?\d*)',
    # Commissioner Sale / Partition format: "Upset Bid Amt. Required $ 136,500.00"
    r'[Uu]pset\s+[Bb]id\s+[Aa]mt\.?\s+[Rr]equired\s*\$\s*([\d,]+\.?\d*)',
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
    # Bidirectional: date appears BEFORE "Last Day to Bid" label (clerk stamp format)
    # Matches: "12/29/2025\nLast Day to Bid:"
    r'(\d{1,2}/\d{1,2}/\d{4})[\s\S]{0,30}?Last\s*Day\s*(?:to|for)?\s*Bid',
    # Written month format: "Last Day for Upset Bid: January 2, 2026" or "Jan 2, 2026"
    r'Last\s+Day\s+(?:for\s+)?Upset\s+Bid[:\s]+([A-Z][a-z]{2,}\s+\d{1,2},?\s+\d{4})',
    # Report of Private Sale (estate sales): "Last Date for upset bids: January 15, 2026"
    r'Last\s+Date\s+for\s+upset\s+bids[:\s]+([A-Z][a-z]{2,}\s+\d{1,2},?\s+\d{4})',
    # Commissioner Sale / Partition format: "Last Day for Upset Bid 1/8/2026" (no colon)
    r'Last\s+Day\s+for\s+Upset\s+Bid\s+(\d{1,2}/\d{1,2}/\d{4})',
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

def extract_property_address(ocr_text: str, return_quality: bool = False) -> Optional[str]:
    """
    Extract property address from OCR text.

    Filters out attorney/law firm addresses to prevent false positives.
    Prioritizes explicit property labels over generic address patterns.

    Args:
        ocr_text: Raw OCR text from document
        return_quality: If True, returns tuple (address, quality_score) where
                       quality_score is the pattern index (lower = higher quality).
                       Patterns 0-7 are explicit labels like "Address of Property:",
                       patterns 8+ are generic patterns that may match mailing addresses.

    Returns:
        Property address string or None if not found.
        If return_quality=True, returns (address, quality_score) or (None, None).
    """
    if not ocr_text:
        return (None, None) if return_quality else None

    # Try each pattern in priority order
    for pattern_idx, pattern_tuple in enumerate(ADDRESS_PATTERNS):
        # Pattern is now a tuple: (regex, label)
        pattern = pattern_tuple[0]
        pattern_label = pattern_tuple[1]

        match = re.search(pattern, ocr_text, re.IGNORECASE | re.MULTILINE)
        if match:
            # Check context 300 characters before the match for rejection patterns
            match_pos = match.start()
            context_start = max(0, match_pos - 300)
            context_text = ocr_text[context_start:match_pos]

            # FIRST: Check for rejection contexts (defendant/heir/attorney addresses)
            is_rejected = False
            for reject_pattern in REJECT_ADDRESS_CONTEXTS:
                if re.search(reject_pattern, context_text, re.IGNORECASE):
                    is_rejected = True
                    logger.debug(f"  Skipping address (found rejection context '{reject_pattern}' near match for pattern '{pattern_label}')")
                    break

            if is_rejected:
                continue

            # SECOND: Check if any attorney indicators appear in the context
            is_attorney_address = False
            for indicator in ATTORNEY_ADDRESS_INDICATORS:
                if indicator.lower() in context_text.lower():
                    is_attorney_address = True
                    logger.debug(f"  Skipping attorney address (found '{indicator}' near match for pattern '{pattern_label}')")
                    break

            # If this is an attorney address, skip it and try the next pattern
            if is_attorney_address:
                continue

            # Handle multi-group patterns (street + city)
            if len(match.groups()) > 1:
                address = f"{match.group(1).strip()}, {match.group(2).strip()}"
            else:
                address = match.group(1).strip()

            # Clean up extra whitespace
            address = re.sub(r'\s+', ' ', address)

            # Strip common address prefixes that shouldn't be part of the address
            # E.g., "commonly known as 88 Maple Springs Ln." -> "88 Maple Springs Ln."
            address_prefixes = [
                r'^commonly\s+known\s+as\s+',
                r'^known\s+as\s+',
            ]
            for prefix_pattern in address_prefixes:
                address = re.sub(prefix_pattern, '', address, flags=re.IGNORECASE)

            # Truncate address after ZIP code to remove legal text that follows
            # E.g., "3017 Forrester St, Durham, NC 27704 hereinafter referred to..."
            # -> "3017 Forrester St, Durham, NC 27704"
            zip_match = re.search(r'(\d{5}(?:-\d{4})?)', address)
            if zip_match:
                zip_end = zip_match.end()
                address = address[:zip_end].strip()

            # CLEAN form artifacts from the address instead of rejecting
            # This handles OCR issues where form text like "Summons Submitted Yes No"
            # appears between street and city/state
            address_lower = address.lower()
            for artifact in FORM_ARTIFACTS:
                if artifact in address_lower:
                    logger.debug(f"  Cleaning form artifact '{artifact}' from address")
                    # Remove the artifact (case-insensitive)
                    address = re.sub(re.escape(artifact), '', address, flags=re.IGNORECASE)
                    address_lower = address.lower()

            # Clean up any resulting extra whitespace after artifact removal
            address = re.sub(r'\s+', ' ', address).strip()

            # If after cleaning we're left with an incomplete address, skip it
            if not address or len(address) < 10:
                logger.debug(f"  Address too short after cleaning artifacts, skipping")
                continue

            # THIRD: Check if captured address CONTAINS legal keywords (garbage text captured inline)
            # This catches cases where OCR text like "Grantors: John Doe" appears within the address
            legal_keywords_in_address = [
                r'[Gg]rantor', r'[Gg]rantee', r'[Tt]rustee',
                r'married\s+(?:man|woman)', r'sole\s+and\s+separate',
                r'his\s+sole', r'her\s+sole', r'a\s+single\s+person'
            ]
            has_legal_keyword = False
            for keyword in legal_keywords_in_address:
                if re.search(keyword, address):
                    has_legal_keyword = True
                    logger.debug(f"  Skipping address with legal keyword '{keyword}' inside: {address}")
                    break

            if has_legal_keyword:
                continue

            logger.debug(f"  Extracted address using pattern '{pattern_label}' (quality={pattern_idx}): {address}")
            return (address, pattern_idx) if return_quality else address

    return (None, None) if return_quality else None


# Threshold for "high quality" address patterns (explicit labels like "Address of Property:")
# Patterns at or below this index are considered high-confidence property addresses
# Patterns above this may match mailing addresses from Certificate of Service, etc.
ADDRESS_QUALITY_THRESHOLD = 12  # Patterns 0-12 are explicit labels, 13+ are generic


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
            except Exception as e:
                logger.debug(f"Bid amount parse failed for '{amount_str}': {e}")
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
            # Try multiple date formats:
            # - %m/%d/%Y: 1/2/2026
            # - %B %d, %Y: January 2, 2026
            # - %B %d %Y: January 2 2026
            # - %b %d, %Y: Jan 2, 2026
            # - %b %d %Y: Jan 2 2026
            for fmt in ['%m/%d/%Y', '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y']:
                try:
                    return datetime.strptime(date_str, fmt)
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
    - Next upset bid deadline (DEPRECATED - see note below)
    - Required deposit amount

    Args:
        ocr_text: Raw OCR text from upset bid document

    Returns:
        Dict with keys: current_bid, previous_bid, minimum_next_bid,
                       next_deadline, deposit_required

    NOTE: The next_deadline field is still extracted but should NOT be used by callers.
    Deadlines should ALWAYS be calculated from the most recent "Upset Bid Filed" event
    date using calculate_upset_bid_deadline(). PDF deadlines may be stale or have OCR errors.
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
            except Exception as e:
                logger.debug(f"Amount conversion failed for '{amount_str}': {e}")
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
            # The amount should be within 50 chars to avoid capturing garbage text
            after_label = ocr_text[min_next_match.end():min_next_match.end()+50]
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
            # Look for ALL dollar amounts after this label (within next line, tightened to 100 chars)
            after_label = ocr_text[deposit_next_match.end():deposit_next_match.end()+100]
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

    # Fallback: If no current_bid but we have minimum_next_bid, back-calculate
    # NC law requires minimum next bid = current bid * 1.05
    if result['current_bid'] is None and result['minimum_next_bid'] is not None:
        result['current_bid'] = round(result['minimum_next_bid'] / Decimal('1.05'), 2)
        logger.debug(f"  Back-calculated current bid from minimum next: ${result['current_bid']}")

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
    Check if the document is a Report of Foreclosure Sale (AOC-SP-301).

    This form is filed after the auction and contains the initial winning bid.

    Args:
        ocr_text: Raw OCR text from document

    Returns:
        True if this appears to be a report of sale
    """
    if not ocr_text:
        return False

    # Strong indicators (form number or title)
    strong_indicators = [
        'AOC-SP-301',
        'REPORT OF FORECLOSURE SALE',
        'Report of Foreclosure Sale',
        'REPORT OF SALE',  # Partition sales also use this format
        'Report of Sale',
    ]

    for indicator in strong_indicators:
        if re.search(indicator, ocr_text, re.IGNORECASE):
            return True

    # Combination indicators (must have multiple)
    weak_indicators = [
        'Date Of Sale',
        'Highest Bid',
        'Amount Bid',
        'Place of Sale',
        'Trustee',
    ]

    match_count = 0
    for indicator in weak_indicators:
        if re.search(indicator, ocr_text, re.IGNORECASE):
            match_count += 1

    # Need at least 2 weak indicators to confirm
    return match_count >= 2


def extract_report_of_sale_data(ocr_text: str) -> Dict[str, Any]:
    """
    Extract all data from an AOC-SP-301 (Report of Foreclosure Sale) form.

    This NC standard form contains:
    - Highest bid amount (the winning bid from the auction - this is the FIRST bid)
    - Date of sale (used to calculate the 10-day upset period deadline)

    Args:
        ocr_text: Raw OCR text from report of sale document

    Returns:
        Dict with keys: initial_bid, sale_date, next_deadline

    NOTE: The next_deadline field is still extracted but should NOT be used by callers.
    Deadlines should ALWAYS be calculated from the most recent "Upset Bid Filed" event
    date using calculate_upset_bid_deadline(). PDF deadlines may be stale or have OCR errors.
    """
    from datetime import timedelta

    result = {
        'initial_bid': None,
        'sale_date': None,
        'next_deadline': None,
    }

    if not ocr_text:
        return result

    def clean_amount(amount_str: str) -> Optional[Decimal]:
        """Clean OCR amount string and convert to Decimal."""
        if not amount_str:
            return None
        # Remove all whitespace and commas
        cleaned = ''.join(c for c in amount_str if c.isdigit() or c == '.')
        if cleaned:
            try:
                amount = Decimal(cleaned)
                # Filter out unreasonable values (less than $100 or more than $100M)
                if 100 <= amount <= 100000000:
                    return amount
            except Exception as e:
                logger.debug(f"Amount conversion failed for '{amount_str}': {e}")
                pass
        return None

    # Extract the highest bid amount
    for pattern in REPORT_OF_SALE_BID_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE | re.DOTALL)
        if match:
            amount = clean_amount(match.group(1))
            if amount:
                result['initial_bid'] = amount
                logger.debug(f"  Found initial bid amount: ${amount}")
                break

    # Fallback: If no direct bid amount found, try to extract "Minimum Amount of Next Upset Bid"
    # and back-calculate the current bid (current_bid = minimum_next_bid / 1.05)
    if result['initial_bid'] is None:
        # Allow 50 chars for whitespace - Tighten proximity window to avoid garbage text
        # Handle OCR typos: "Upsat" instead of "Upset"
        minimum_next_pattern = r'Minimum\s+Amount.*?(?:of\s+)?Next\s+Ups[ae]t\s+Bid[\s\S]{0,50}?\$?\s*(\d[\d,\.\s]+\.\d{2})'
        match = re.search(minimum_next_pattern, ocr_text, re.IGNORECASE | re.DOTALL)
        if match:
            minimum_next_bid = clean_amount(match.group(1))
            if minimum_next_bid:
                # Back-calculate current bid: current_bid = minimum_next_bid / 1.05
                result['initial_bid'] = round(minimum_next_bid / Decimal('1.05'), 2)
                logger.debug(f"  No direct bid found, back-calculated from minimum next bid ${minimum_next_bid}: ${result['initial_bid']}")

    # Extract the date of sale
    for pattern in REPORT_OF_SALE_DATE_PATTERNS:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            # Try multiple date formats (numeric and written month formats)
            for fmt in ['%m/%d/%Y', '%B %d, %Y', '%B %d %Y']:
                try:
                    sale_date = datetime.strptime(date_str, fmt)
                    result['sale_date'] = sale_date.date()
                    # Calculate the upset bid deadline (10 days from sale date, adjusted for weekends/holidays)
                    adjusted_deadline = calculate_upset_bid_deadline(sale_date.date())
                    result['next_deadline'] = datetime.combine(adjusted_deadline, datetime.min.time())
                    logger.debug(f"  Found sale date: {result['sale_date']}, deadline: {adjusted_deadline}")
                    break
                except ValueError:
                    continue
            # If date was successfully parsed, exit the outer loop
            if result['sale_date']:
                break

    return result


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

    # Prioritized bid extraction:
    # 1. Check if this is an Upset Bid document (AOC-SP-403) - highest priority
    # 2. Check if this is a Report of Sale document (AOC-SP-301) - medium priority
    # 3. Fall back to generic bid extraction - lowest priority
    bid_amount = None

    if is_upset_bid_document(ocr_text):
        # Extract from upset bid document - use current_bid field
        upset_data = extract_upset_bid_data(ocr_text)
        bid_amount = upset_data.get('current_bid')
        logger.debug(f"  Extracted bid from upset bid document: {bid_amount}")

    if not bid_amount and is_report_of_sale_document(ocr_text):
        # Extract from report of sale - use initial_bid field
        sale_data = extract_report_of_sale_data(ocr_text)
        bid_amount = sale_data.get('initial_bid')
        logger.debug(f"  Extracted bid from report of sale: {bid_amount}")

    if not bid_amount:
        # Fall back to generic extraction
        bid_amount = extract_bid_amount(ocr_text)
        if bid_amount:
            logger.debug(f"  Extracted bid from generic pattern: {bid_amount}")

    return {
        'property_address': extract_property_address(ocr_text),
        'current_bid_amount': bid_amount,
        'next_bid_deadline': extract_upset_deadline(ocr_text),
        'sale_date': extract_sale_date(ocr_text),
        'legal_description': extract_legal_description(ocr_text),
        'trustee_name': extract_trustee_name(ocr_text),
        'attorney_name': attorney_info.get('name'),
        'attorney_phone': attorney_info.get('phone'),
        'attorney_email': attorney_info.get('email'),
    }


def _get_document_priority(file_path: str) -> int:
    """
    Get priority score for a document based on filename.
    Lower score = higher priority for address extraction.
    """
    if not file_path:
        return len(ADDRESS_DOCUMENT_PRIORITY)

    filename_lower = file_path.lower()
    for i, keyword in enumerate(ADDRESS_DOCUMENT_PRIORITY):
        if keyword in filename_lower:
            return i
    return len(ADDRESS_DOCUMENT_PRIORITY)  # Lowest priority


def _find_address_in_documents(documents: list, return_quality: bool = False):
    """
    Search documents in priority order for property address.

    Tries each document until a valid property address is found.
    Documents are sorted by type priority (foreclosure notices first,
    then sale docs, then affidavits, then others).

    Args:
        documents: List of Document objects with ocr_text
        return_quality: If True, returns (address, quality_score) tuple

    Returns:
        Property address string or None if not found in any document.
        If return_quality=True, returns (address, quality_score) or (None, None).
    """
    # Sort documents by priority (foreclosure notices first)
    sorted_docs = sorted(documents, key=lambda d: _get_document_priority(d.file_path))

    # Try each document until we find an address
    for doc in sorted_docs:
        if not doc.ocr_text:
            continue

        result = extract_property_address(doc.ocr_text, return_quality=True)
        address, quality = result
        if address:
            logger.info(f"  Found address in {doc.file_path} (quality={quality}): {address}")
            return (address, quality) if return_quality else address

    return (None, None) if return_quality else None


def _find_bid_in_event_descriptions(case_id: int) -> Optional[Decimal]:
    """
    Search event descriptions for bid amounts.

    Event descriptions for "Upset Bid Filed" and "Report of Sale" events often
    contain the bid amount directly, e.g.:
    - "Bid Amount $9,830.00 Deposit Amount $750.00 and Emailed confirmation."
    - "Property sold for $125,000.00"

    This is often more reliable than OCR extraction from PDFs.

    Args:
        case_id: Database ID of the case

    Returns:
        Bid amount as Decimal or None if not found
    """
    # Event types that commonly contain bid amounts in their descriptions
    BID_EVENT_TYPES = [
        'upset bid filed',
        'report of sale',
        'report of foreclosure sale',
    ]

    # Patterns to match bid amounts in event descriptions
    BID_DESCRIPTION_PATTERNS = [
        r'[Bb]id\s+[Aa]m(?:oun)?t[:\s]*\$?\s*([\d,]+\.?\d*)',  # "Bid Amount $9,830.00" or "Bid Amt: $135,000"
        r'[Ss]old\s+for\s*\$?\s*([\d,]+\.?\d*)',  # "sold for $125,000"
        r'[Aa]m(?:oun)?t\s+[Bb]id\s*\$?\s*([\d,]+\.?\d*)',  # "Amount Bid $50,000" or "Amt Bid"
        r'\$\s*([\d,]+\.\d{2})\s+[Bb]id',  # "$9,830.00 Bid"
        r'[Uu]pset\s+[Bb]id\s+[Aa]m(?:oun)?t[:\s]*\$?\s*([\d,]+\.?\d*)',  # "Upset Bid Amount $57,881.25"
        r'^\$\s*([\d,]+\.\d{2})\s+[A-Z]',  # "$294,275.00 Billy Finch" - amount at start followed by name
    ]

    with get_session() as session:
        # First get the case's sale_date to filter to current sale cycle
        case = session.query(Case).filter_by(id=case_id).first()
        sale_date = case.sale_date if case else None

        # Build query for events ordered by date descending (most recent first)
        # We want the MOST RECENT bid, not the highest, because:
        # 1. Upset bids should always increase (NC law requires 5% increase)
        # 2. The current bid is always the most recent one filed
        query = session.query(CaseEvent).filter_by(case_id=case_id)

        # CRITICAL: Filter to current sale cycle only
        # For resale cases, we must ignore bids from voided/set-aside sales
        if sale_date:
            query = query.filter(CaseEvent.event_date >= sale_date)

        events = query.order_by(
            CaseEvent.event_date.desc().nullslast(),
            CaseEvent.id.desc()  # Secondary sort by ID for same-date events
        ).all()

        for event in events:
            if not event.event_description:
                continue

            # Check if this event type commonly contains bid amounts
            event_type_lower = (event.event_type or '').lower()
            if not any(bid_type in event_type_lower for bid_type in BID_EVENT_TYPES):
                continue

            # Try each pattern
            for pattern in BID_DESCRIPTION_PATTERNS:
                match = re.search(pattern, event.event_description)
                if match:
                    amount = clean_amount(match.group(1))
                    if amount and amount > 0:
                        # Return the MOST RECENT bid (first match since ordered by date DESC)
                        logger.info(f"  Found bid ${amount} in event description (date={event.event_date}): {event.event_description[:50]}...")
                        return amount

        return None


def _find_address_in_event_descriptions(case_id: int) -> Optional[str]:
    """
    Search event descriptions for property addresses.

    For Petition to Sell and other special proceeding cases, the property address
    often appears in the event description on the portal (e.g., "Report of Sale"
    events show "1508 Beacon Village Drive, Raleigh 27604").

    Args:
        case_id: Database ID of the case

    Returns:
        Property address string or None if not found
    """
    # Event types that commonly contain property addresses in their descriptions
    ADDRESS_EVENT_TYPES = [
        'report of sale',
        'petition to sell',
        'notice of sale',
        'order confirming sale',
    ]

    # Pattern to match addresses in event descriptions
    # Format: "123 Street Name, City 12345" or "123 Street Name, City, NC 12345"
    # Note: Allows periods in street names (e.g., "W. Lake Anne Drive")
    EVENT_ADDRESS_PATTERN = re.compile(
        r'(\d+\s+[A-Za-z0-9\s\.]+(?:Street|St|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|'
        r'Circle|Cir|Way|Avenue|Ave|Boulevard|Blvd|Place|Pl|Terrace|Ter|Trail|Trl|'
        r'Village|Villiage)[,\s]+[A-Za-z\s]+(?:,\s*NC)?\s*\d{5}(?:-\d{4})?)',
        re.IGNORECASE
    )

    with get_session() as session:
        # Get events ordered by date descending (most recent first)
        # We want the MOST RECENT address because:
        # 1. Property addresses don't change during a case
        # 2. More recent events may have better formatting or corrections
        # 3. Consistent with _find_bid_in_event_descriptions pattern
        events = session.query(CaseEvent).filter_by(case_id=case_id).order_by(
            CaseEvent.event_date.desc().nullslast(),
            CaseEvent.id.desc()  # Secondary sort by ID for same-date events
        ).all()

        for event in events:
            if not event.event_description:
                continue

            # Check if this event type commonly contains addresses
            event_type_lower = (event.event_type or '').lower()
            if not any(addr_type in event_type_lower for addr_type in ADDRESS_EVENT_TYPES):
                continue

            # Check if the description looks like an address
            desc = event.event_description.strip()
            match = EVENT_ADDRESS_PATTERN.search(desc)  # Use search() not match() to find anywhere in string
            if match:
                address = match.group(1).strip()
                # Return the MOST RECENT address (first match since ordered by date DESC)
                logger.info(f"  Found address in event description (date={event.event_date}, {event.event_type}): {address}")
                return address

    return None


def extract_all_from_case(case_id: int) -> Dict[str, Any]:
    """
    Extract all available data from all documents for a case.

    Combines data from all documents, preferring non-null values.
    For property addresses, searches ALL documents in priority order
    until a valid address is found.

    Args:
        case_id: Database ID of the case

    Returns:
        Dict with all extracted fields (best values from all documents).
        Includes 'address_quality' (int) where lower is better quality.
        Quality 0-12 = explicit labels ("Address of Property:"), 13+ = generic patterns.
    """
    result = {
        'property_address': None,
        'address_quality': None,  # Lower = higher quality (explicit labels)
        'current_bid_amount': None,
        'next_bid_deadline': None,
        'sale_date': None,
        'legal_description': None,
        'trustee_name': None,
        'attorney_name': None,
        'attorney_phone': None,
        'attorney_email': None,
    }

    # First, check case type (separate session to avoid detached instance issues)
    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        is_special_proceeding = case and case.case_type == 'Special Proceeding'

    # For Special Proceedings (Petition to Sell), check event descriptions FIRST
    # These often have property addresses in Report of Sale event descriptions
    if is_special_proceeding:
        result['property_address'] = _find_address_in_event_descriptions(case_id)
        if result['property_address']:
            result['address_quality'] = 0  # Event descriptions are high quality

    # PRIORITY 1: Event descriptions are the authoritative source for bid amounts
    # Check event descriptions BEFORE OCR extraction to prevent garbage OCR from being used
    # Event descriptions come directly from the court portal as structured data, while OCR
    # can produce wildly incorrect values from garbled text (e.g., phone numbers
    # or malformed amounts like "M94 512 26.90" becoming $9,451,226.90)
    event_bid = _find_bid_in_event_descriptions(case_id)
    if event_bid:
        result['current_bid_amount'] = event_bid
        logger.debug(f"  Using authoritative event bid: ${event_bid}")

    # For property_address: search ALL documents in priority order
    with get_session() as session:
        # Get the case's sale_date to filter documents for resale cases
        case = session.query(Case).filter_by(id=case_id).first()
        case_sale_date = case.sale_date if case else None

        # Get documents ordered by creation date descending (most recent first)
        # Process documents in chronological order (newest first) for two reasons:
        # 1. For cumulative fields (sale_date, etc), most recent data is authoritative
        # 2. Break on first valid result to avoid processing unnecessary older documents
        documents = session.query(Document).filter_by(case_id=case_id).order_by(
            Document.created_at.desc().nullslast(),
            Document.id.desc()  # Secondary sort by ID for same-timestamp documents
        ).all()

        if not result['property_address']:
            addr, quality = _find_address_in_documents(documents, return_quality=True)
            result['property_address'] = addr
            result['address_quality'] = quality

        # For other fields: use first non-null value from any document
        # SKIP current_bid_amount if event bid already found (event bid is authoritative)
        # SKIP documents from before sale_date (for resale cases, old docs have stale data)
        # Process documents in chronological order (newest first) so most recent values win
        for doc in documents:
            if not doc.ocr_text:
                continue

            # For resale cases: skip documents from before sale_date for bid/sale data
            # These old documents contain stale data from voided/set-aside sales
            # Note: We still process old docs for addresses, trustee info, etc. which don't change
            # Also skip documents with unknown dates when we have a sale_date - these are likely old
            doc_is_from_old_sale = False
            if case_sale_date:
                if doc.document_date:
                    if doc.document_date < case_sale_date:
                        doc_is_from_old_sale = True
                elif doc.document_name and doc.document_name.startswith('unknown'):
                    # "unknown__*.pdf" files don't have dates - skip for bid data in resale cases
                    doc_is_from_old_sale = True

            doc_data = extract_from_document(doc.ocr_text)

            # Merge data, preferring non-null values
            for key, value in doc_data.items():
                if key == 'property_address':
                    continue  # Already handled with priority search above
                if key == 'current_bid_amount' and event_bid:
                    # Cross-validate OCR bid against authoritative event bid
                    if value and abs(value - event_bid) > event_bid * Decimal('0.1'):
                        logger.warning(f"  OCR bid discrepancy for case {case_id}: OCR=${value}, Event=${event_bid} (>10% diff). Using event bid.")
                    continue  # Skip OCR bid - event bid already set
                # Skip bid/sale data from documents predating current sale (resale protection)
                if doc_is_from_old_sale and key in ('current_bid_amount', 'sale_date'):
                    continue
                if value is not None and result[key] is None:
                    result[key] = value

    # Fallback: check event descriptions for addresses (for non-special-proceeding cases)
    if not result['property_address']:
        result['property_address'] = _find_address_in_event_descriptions(case_id)

    # Final fallback: Use Claude Vision OCR for Report of Sale / Upset Bid documents
    # This handles cases where Tesseract fails to read handwritten bid amounts
    if result['current_bid_amount'] is None:
        result = _try_vision_ocr_fallback(case_id, result)

    return result


def _try_vision_ocr_fallback(case_id: int, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Try Claude Vision OCR as a last resort for extracting bid data.

    Only runs on Report of Sale and Upset Bid documents when regular
    extraction failed to find a bid amount.

    Args:
        case_id: Database ID of the case
        result: Current extraction result dict

    Returns:
        Updated result dict with any data found via vision OCR
    """
    try:
        from ocr.vision_ocr import (
            extract_bid_data_with_vision,
            should_use_vision_fallback,
            _is_vision_ocr_document
        )
    except ImportError:
        logger.debug("Vision OCR module not available")
        return result

    with get_session() as session:
        # Get case's sale_date for filtering (resale protection)
        case = session.query(Case).filter_by(id=case_id).first()
        case_sale_date = case.sale_date if case else None

        documents = session.query(Document).filter_by(case_id=case_id).all()

        for doc in documents:
            # Only try vision OCR on relevant document types
            if not _is_vision_ocr_document(doc.document_name):
                continue

            # For resale cases: skip documents from before current sale_date
            # These contain stale bid data from voided/set-aside sales
            if case_sale_date:
                if doc.document_date and doc.document_date < case_sale_date:
                    logger.debug(f"  Skipping Vision OCR for {doc.document_name} - document_date {doc.document_date} < sale_date {case_sale_date}")
                    continue
                elif doc.document_name and doc.document_name.startswith('unknown'):
                    logger.debug(f"  Skipping Vision OCR for {doc.document_name} - unknown date document in resale case")
                    continue

            # Check if we should use fallback based on Tesseract output
            if not doc.ocr_text:
                continue

            if not should_use_vision_fallback(doc.document_name, doc.ocr_text, result.get('current_bid_amount')):
                continue

            # Make sure file exists
            if not doc.file_path or not os.path.exists(doc.file_path):
                continue

            logger.info(f"  Trying Claude Vision OCR fallback for {doc.document_name}")

            # Run vision OCR
            vision_data = extract_bid_data_with_vision(doc.file_path)

            # Update result with any found data
            if vision_data.get('bid_amount') and result['current_bid_amount'] is None:
                result['current_bid_amount'] = vision_data['bid_amount']
                logger.info(f"  Vision OCR found bid amount: ${vision_data['bid_amount']}")

            # If we found a bid, we're done
            if result['current_bid_amount'] is not None:
                break

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
            # All fields are now "sticky" - once set, never overwritten
            updated_fields = []

            # Address is STICKY - only set if not already present
            # Manual corrections are preserved; use reprocess_case() for full reset
            if extracted['property_address'] and not case.property_address:
                case.property_address = extracted['property_address']
                logger.info(f"  Set property address: {extracted['property_address'][:50]}...")
                updated_fields.append('property_address')
            elif extracted['property_address'] and case.property_address:
                logger.debug(f"  Preserving existing address (sticky): {case.property_address[:50]}...")

            # Current bid: Update if we have new data AND it differs from existing
            # IMPORTANT: We don't use ">" comparison because extract_all_from_case()
            # already returns the MOST RECENT bid (from chronologically ordered events).
            # The most recent bid is authoritative, even if it's somehow lower (rare edge case).
            # Trust the extraction layer's chronology, don't second-guess with value comparison.
            if extracted['current_bid_amount'] and extracted['current_bid_amount'] != case.current_bid_amount:
                old_amount = case.current_bid_amount
                case.current_bid_amount = extracted['current_bid_amount']
                # NC law: minimum next bid is 5% higher than current bid
                case.minimum_next_bid = round(extracted['current_bid_amount'] * Decimal('1.05'), 2)
                if old_amount:
                    updated_fields.append(f'current_bid_amount (updated: ${old_amount} -> ${extracted["current_bid_amount"]})')
                    updated_fields.append(f'minimum_next_bid (updated: ${round(old_amount * Decimal("1.05"), 2)} -> ${case.minimum_next_bid})')
                else:
                    updated_fields.append('current_bid_amount')
                    updated_fields.append('minimum_next_bid')

            # NOTE: next_bid_deadline is NOT populated from OCR extraction.
            # Deadlines MUST be calculated from event dates using business day logic.
            # OCR data may come from old documents (voided/set-aside sales) and be incorrect.
            # The deadline is calculated by:
            # - case_monitor.py (from most recent "Upset Bid Filed" event date)
            # - classifier.py (stale deadline fix logic)
            # See also: case_monitor.py update_case_with_pdf_bid_data() comments

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
                success = True
            else:
                logger.debug(f"  No new data for case {case_id}")
                success = False

        # Mark documents as extraction-attempted (success or failure)
        with get_session() as session:
            session.query(Document).filter(
                Document.case_id == case_id,
                Document.ocr_text.isnot(None),
                Document.extraction_attempted_at.is_(None)
            ).update({'extraction_attempted_at': datetime.now()})
            session.commit()

        return success

    except Exception as e:
        logger.error(f"  Error extracting data for case {case_id}: {e}")
        # Still mark as attempted even on failure
        try:
            with get_session() as session:
                session.query(Document).filter(
                    Document.case_id == case_id,
                    Document.ocr_text.isnot(None),
                    Document.extraction_attempted_at.is_(None)
                ).update({'extraction_attempted_at': datetime.now()})
                session.commit()
        except Exception as mark_error:
            logger.error(f"  Failed to mark extraction attempt for case {case_id}: {mark_error}")
        return False


def get_documents_needing_extraction() -> List[int]:
    """
    Find case IDs with OCR text but no extraction attempt.

    Returns:
        List of case IDs that need extraction processing
    """
    with get_session() as session:
        case_ids = session.query(Document.case_id).filter(
            Document.ocr_text.isnot(None),
            Document.extraction_attempted_at.is_(None)
        ).distinct().all()
        return [c[0] for c in case_ids if c[0]]


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
