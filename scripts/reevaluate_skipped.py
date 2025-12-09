#!/usr/bin/env python3
"""Re-evaluate skipped cases against updated indicators."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import SkippedCase
from scraper.page_parser import is_foreclosure_case
from common.logger import setup_logger

logger = setup_logger(__name__)

def reevaluate_skipped_cases():
    """Re-evaluate all pending skipped cases against current indicators."""
    with get_session() as session:
        # Get all skipped cases that haven't been reviewed
        skipped = session.query(SkippedCase).filter(
            SkippedCase.review_action.is_(None)
        ).all()

        logger.info(f"Found {len(skipped)} skipped cases to re-evaluate")

        flagged = 0
        for case in skipped:
            # Ensure events is a list of dicts (handle malformed data)
            events = case.events_json or []
            if isinstance(events, list):
                events = [e for e in events if isinstance(e, dict)]
            else:
                events = []

            # Reconstruct case_data for is_foreclosure_case()
            case_data = {
                'case_type': case.case_type or '',
                'events': events
            }

            # Check if it now matches
            try:
                if is_foreclosure_case(case_data):
                    case.review_action = 'flagged_for_review'
                    flagged += 1
                    logger.info(f"Flagged: {case.case_number} - {case.case_type}")
            except Exception as e:
                logger.warning(f"Error checking {case.case_number}: {e}")

        session.commit()

        logger.info(f"Re-evaluation complete: {flagged} of {len(skipped)} cases flagged for review")
        return flagged, len(skipped)

if __name__ == '__main__':
    flagged, total = reevaluate_skipped_cases()
    print(f"\nRe-evaluation Results:")
    print(f"  Total skipped cases: {total}")
    print(f"  Flagged for review: {flagged}")
