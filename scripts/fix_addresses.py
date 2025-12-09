#!/usr/bin/env python3
"""Fix malformed addresses containing form artifacts."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import Case
from extraction.extractor import extract_property_address
from common.logger import setup_logger

logger = setup_logger(__name__)

def fix_malformed_addresses():
    """Find and fix addresses containing form artifacts."""
    with get_session() as session:
        # Find cases with malformed addresses
        cases = session.query(Case).filter(
            Case.property_address.ilike('%summons submitted%')
        ).all()

        logger.info(f"Found {len(cases)} cases with malformed addresses")

        fixed = 0
        for case in cases:
            old_address = case.property_address
            logger.info(f"Case {case.case_number}: {old_address}")

            # Clear the address so extraction can re-run
            case.property_address = None

            # Note: Re-extraction would need OCR text from documents
            # For now, just clear the bad address
            fixed += 1
            logger.info(f"  Cleared malformed address")

        session.commit()
        logger.info(f"Fixed {fixed} addresses")
        return fixed

if __name__ == '__main__':
    fixed = fix_malformed_addresses()
    print(f"Fixed {fixed} malformed addresses")
