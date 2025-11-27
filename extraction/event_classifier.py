"""Event-based case classifier.

Classifies foreclosure cases based on case events without requiring OCR.

Classification Logic:
- upset_bid: Has "Report Of Foreclosure Sale" (auction occurred, in 10-day upset period)
- upcoming: Has "Findings And Order Of Foreclosure" but NO "Report Of Foreclosure Sale"
- pending: Has "Foreclosure Case Initiated" but NO "Findings And Order Of Foreclosure"
- needs_review: Edge cases (bankruptcy, dismissals, etc.)
"""

import argparse
from sqlalchemy import text
from database.connection import get_session
from common.logger import setup_logger

logger = setup_logger(__name__)

# Key events that determine case status
# These indicate an auction has occurred and property is in upset bid period
SALE_EVENTS = [
    'Report of Sale',
    'Report Of Foreclosure Sale',
    'Report Of Foreclosure Sale (Chapter 45)',
    'Report of Foreclosure Sale',
    'Trustee Report of Sale',  # Catches variations like "Trustee Brown Report of Sale"
]

ORDER_EVENTS = [
    'Findings And Order Of Foreclosure',
]

INITIATED_EVENTS = [
    'Foreclosure Case Initiated',
]

# Events that may indicate complications requiring review
COMPLICATION_EVENTS = [
    'Bankruptcy',
    'Motion to Dismiss',
    'Dismissed',
    'Voluntary Dismissal',
    'Order of Dismissal',
    'Stay',
]


def get_case_events(session, case_id):
    """Get all events for a case."""
    result = session.execute(
        text("SELECT event_type FROM case_events WHERE case_id = :case_id"),
        {"case_id": case_id}
    )
    return [row[0] for row in result.fetchall() if row[0]]


def classify_case(events):
    """
    Classify a case based on its events.

    Args:
        events: List of event_type strings for the case

    Returns:
        tuple: (classification, reason)
    """
    events_lower = [e.lower() if e else '' for e in events]
    events_set = set(events_lower)

    # Check for sale events (Report Of Foreclosure Sale)
    has_sale = any(
        sale.lower() in events_set or any(sale.lower() in e for e in events_lower)
        for sale in SALE_EVENTS
    )

    # Check for order of foreclosure
    has_order = any(
        order.lower() in events_set or any(order.lower() in e for e in events_lower)
        for order in ORDER_EVENTS
    )

    # Check for case initiation
    has_initiated = any(
        init.lower() in events_set or any(init.lower() in e for e in events_lower)
        for init in INITIATED_EVENTS
    )

    # Check for complications
    has_complications = any(
        comp.lower() in events_set or any(comp.lower() in e for e in events_lower)
        for comp in COMPLICATION_EVENTS
    )

    # Classification logic
    if has_sale:
        if has_complications:
            return 'needs_review', 'Has sale but also has complications (bankruptcy/dismissal)'
        return 'upset_bid', 'Auction occurred - in upset bid period'

    if has_order:
        if has_complications:
            return 'needs_review', 'Has foreclosure order but also has complications'
        return 'upcoming', 'Foreclosure ordered - awaiting auction'

    if has_initiated:
        if has_complications:
            return 'needs_review', 'Case initiated but has complications'
        return 'pending', 'Case initiated - awaiting court order'

    # No key events found
    return 'needs_review', 'No key foreclosure events found'


def run_classification(dry_run=False, limit=None):
    """
    Run classification on all cases.

    Args:
        dry_run: If True, don't update database
        limit: Limit number of cases to process (for testing)
    """
    with get_session() as session:
        # Get all cases
        query = "SELECT id, case_number FROM cases"
        if limit:
            query += f" LIMIT {limit}"

        result = session.execute(text(query))
        cases = list(result)

        logger.info(f"Processing {len(cases)} cases...")

        # Track statistics
        stats = {
            'upset_bid': 0,
            'upcoming': 0,
            'pending': 0,
            'needs_review': 0,
        }

        for case_id, case_number in cases:
            events = get_case_events(session, case_id)
            classification, reason = classify_case(events)

            stats[classification] += 1

            if not dry_run:
                session.execute(
                    text("UPDATE cases SET classification = :classification WHERE id = :id"),
                    {"classification": classification, "id": case_id}
                )

            logger.debug(f"{case_number}: {classification} - {reason}")

        if dry_run:
            logger.info("DRY RUN - no changes made")
            session.rollback()
        else:
            logger.info("Classifications saved to database")

        # Print summary
        logger.info("=" * 50)
        logger.info("CLASSIFICATION SUMMARY")
        logger.info("=" * 50)
        for classification, count in sorted(stats.items(), key=lambda x: -x[1]):
            pct = (count / len(cases) * 100) if cases else 0
            logger.info(f"  {classification}: {count} ({pct:.1f}%)")
        logger.info(f"  TOTAL: {len(cases)}")
        logger.info("=" * 50)

        return stats


def main():
    parser = argparse.ArgumentParser(description='Classify cases based on events')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview classifications without updating database')
    parser.add_argument('--limit', type=int,
                        help='Limit number of cases to process (for testing)')

    args = parser.parse_args()

    run_classification(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
