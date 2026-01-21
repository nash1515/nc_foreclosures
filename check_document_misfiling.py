#!/usr/bin/env python3
"""
Check for document misfiling issues where OCR text contains a different case number
than the case the document is attached to.
"""

import re
import sys
from database.connection import get_session
from database.models import Case, Document
from sqlalchemy import and_

def extract_case_numbers(text):
    """Extract all case numbers from OCR text."""
    if not text:
        return []

    # Pattern to match case numbers like "25SP001234" or "25 SP 001234" or "25SP 001234"
    # Allow optional spaces and zeros
    pattern = r'\b(\d{2})\s*SP\s*0*(\d{3,6})(?:-(\d{3}))?\b'
    matches = re.findall(pattern, text, re.IGNORECASE)

    # Format as standardized case numbers
    case_numbers = []
    for match in matches:
        year = match[0]
        case_num = match[1].zfill(6)  # Pad to 6 digits
        county = match[2] if match[2] else ''

        if county:
            formatted = f"{year}SP{case_num}-{county}"
        else:
            # Just the base case number without county code
            formatted = f"{year}SP{case_num}"

        case_numbers.append(formatted)

    return list(set(case_numbers))  # Remove duplicates

def extract_respondent_name(style):
    """Extract the respondent/defendant name from the case style."""
    if not style:
        return None

    # Pattern: "FORECLOSURE... - Name" or "FORECLOSURE... Name"
    # Extract everything after "FORECLOSURE" and common prefixes
    style = style.strip()

    # Remove common prefixes
    style = re.sub(r'^FORECLOSURE\s+OF\s+A\s+DEED\s+OF\s+TRUST\s+', '', style, flags=re.IGNORECASE)
    style = re.sub(r'^FORECLOSURE\s*-?\s*', '', style, flags=re.IGNORECASE)
    style = re.sub(r'^\(HOA\)\s*-?\s*', '', style, flags=re.IGNORECASE)

    # Clean up
    name = style.strip()
    if not name:
        return None

    # Extract last name (usually first word or two)
    # Handle cases like "Brandon S. Roe" -> "Roe"
    parts = name.split()
    if len(parts) >= 2:
        # Return last name (last part)
        return parts[-1].upper()
    elif len(parts) == 1:
        return parts[0].upper()

    return None

def check_misfiling():
    """Check all upset_bid Report of Sale documents for mismatched case numbers."""
    with get_session() as session:
        # Get all Report of Sale documents for upset_bid cases
        documents = session.query(Document, Case).join(
            Case, Document.case_id == Case.id
        ).filter(
            and_(
                Case.classification == 'upset_bid',
                Document.document_name.like('%Report%Sale%'),
                Document.ocr_text.isnot(None),
                Document.ocr_text != ''
            )
        ).order_by(Case.case_number).all()

        total_checked = 0
        mismatches = []

        for doc, case in documents:
            total_checked += 1

            # Extract case numbers from OCR
            ocr_case_numbers = extract_case_numbers(doc.ocr_text)

            # Check if the actual case number is in the OCR text
            # Strip county code for comparison since OCR might not have it
            base_case = case.case_number.split('-')[0]  # e.g., "25SP001024"

            # Filter OCR case numbers to only those that don't match
            mismatched = [ocr_num for ocr_num in ocr_case_numbers
                          if not ocr_num.startswith(base_case) and base_case not in ocr_num]

            # Also check for party name mismatch
            expected_name = extract_respondent_name(case.style)
            name_mismatch = False
            name_mismatch_details = None

            if expected_name and len(expected_name) > 3:  # Only check meaningful names
                # Check if the expected name appears in OCR
                if expected_name not in doc.ocr_text.upper():
                    # Name doesn't appear - might be wrong document
                    # But check if there are other recognizable names (heuristic)
                    # Look for pattern "Respondent:" or "Defendant:" followed by a name
                    respondent_pattern = r'(?:Respondent|Defendant):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'
                    found_names = re.findall(respondent_pattern, doc.ocr_text)
                    if found_names:
                        name_mismatch = True
                        name_mismatch_details = {
                            'expected_name': expected_name,
                            'found_names': found_names
                        }

            if mismatched or name_mismatch:
                # Check if the mismatched number appears prominently (multiple times or early in doc)
                ocr_lower = doc.ocr_text.lower()
                mismatch_counts = {}
                for mis_num in mismatched:
                    # Count occurrences
                    count = len(re.findall(re.escape(mis_num.replace('0', '0*')), ocr_lower, re.IGNORECASE))
                    if count > 0:
                        mismatch_counts[mis_num] = count

                if mismatch_counts or name_mismatch:
                    mismatch_info = {
                        'case_number': case.case_number,
                        'style': case.style,
                        'doc_id': doc.id,
                        'doc_name': doc.document_name,
                        'expected': case.case_number,
                        'ocr_length': len(doc.ocr_text)
                    }

                    if mismatch_counts:
                        mismatch_info['found_in_ocr'] = mismatch_counts
                    if name_mismatch_details:
                        mismatch_info['name_mismatch'] = name_mismatch_details

                    mismatches.append(mismatch_info)

    # Print results
    print(f"\n{'='*80}")
    print(f"Document Misfiling Check Results")
    print(f"{'='*80}")
    print(f"\nTotal cases checked: {total_checked}")
    print(f"Potential mismatches found: {len(mismatches)}\n")

    if mismatches:
        print(f"{'='*80}")
        print("POTENTIAL MISFILING ISSUES:")
        print(f"{'='*80}\n")

        for i, mismatch in enumerate(mismatches, 1):
            print(f"{i}. Case: {mismatch['case_number']}")
            print(f"   Style: {mismatch['style']}")
            print(f"   Document: {mismatch['doc_name']} (ID: {mismatch['doc_id']})")
            print(f"   OCR length: {mismatch['ocr_length']:,} chars")
            print(f"   Expected case #: {mismatch['expected']}")

            if 'found_in_ocr' in mismatch:
                print(f"   Case number mismatches found in OCR:")
                for case_num, count in mismatch['found_in_ocr'].items():
                    print(f"      - {case_num} (appears {count} time(s))")

            if 'name_mismatch' in mismatch:
                print(f"   Party name mismatch:")
                print(f"      Expected: {mismatch['name_mismatch']['expected_name']}")
                print(f"      Found: {', '.join(mismatch['name_mismatch']['found_names'])}")

            print()
    else:
        print("No misfiling issues detected!")

    return total_checked, len(mismatches), mismatches

if __name__ == '__main__':
    try:
        total, mismatch_count, mismatches = check_misfiling()
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
