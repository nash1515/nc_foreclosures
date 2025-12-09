#!/usr/bin/env python3
"""Backfill missing deadlines for upset_bid cases."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from database.connection import get_session
from database.models import Case, CaseEvent
from common.business_days import calculate_upset_bid_deadline
from common.logger import setup_logger

logger = setup_logger(__name__)

SALE_EVENT_TYPES = [
    'report of foreclosure sale',
    'report of sale',
]

def fix_missing_deadlines():
    """Find upset_bid cases with NULL deadlines and calculate from sale events."""
    with get_session() as session:
        # Find upset_bid cases missing deadline
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.next_bid_deadline.is_(None)
        ).all()

        logger.info(f"Found {len(cases)} upset_bid cases with missing deadlines")

        fixed = 0
        for case in cases:
            # Find the most recent sale event
            sale_event = session.query(CaseEvent).filter(
                CaseEvent.case_id == case.id,
                CaseEvent.event_date.isnot(None)
            ).filter(
                CaseEvent.event_type.ilike('%sale%')
            ).order_by(CaseEvent.event_date.desc()).first()

            if sale_event and sale_event.event_date:
                deadline = calculate_upset_bid_deadline(sale_event.event_date)
                case.next_bid_deadline = datetime.combine(deadline, datetime.min.time())
                case.sale_date = sale_event.event_date
                fixed += 1
                logger.info(f"Case {case.case_number}: sale={sale_event.event_date}, deadline={deadline}")
            else:
                logger.warning(f"Case {case.case_number}: no sale event found")

        session.commit()
        logger.info(f"Fixed {fixed} deadlines")
        return fixed

if __name__ == '__main__':
    fixed = fix_missing_deadlines()
    print(f"\nFixed {fixed} missing deadlines")
