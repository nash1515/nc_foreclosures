"""Case status classification based on events and case type.

Classification states:
- 'upcoming': Foreclosure initiated, no sale report yet
- 'upset_bid': Has sale report AND within 10-day upset period
- 'blocked': Bankruptcy or stay in effect (check for updates during daily scrape)
- 'closed_sold': Sale completed, past upset period
- 'closed_dismissed': Case dismissed/terminated
"""

from datetime import datetime, timedelta
from typing import Optional, List

from database.connection import get_session
from database.models import Case, CaseEvent, Document
from common.logger import setup_logger

logger = setup_logger(__name__)


# =============================================================================
# EVENT TYPE CONSTANTS
# =============================================================================

# Events indicating a sale has occurred
SALE_REPORT_EVENTS = [
    'report of foreclosure sale',
    'report of sale',
    'foreclosure sale report',
    'report of foreclosure sale (chapter 45)',
]

# Events that BLOCK the foreclosure (bankruptcy stay - may resume later)
# Note: We check for these BUT exclude "resolved", "relief", "dismissal of bankruptcy"
BANKRUPTCY_EVENTS = [
    'bankruptcy',
    'bankruptcy filed',
    'notice of bankruptcy',
    'suggestion of bankruptcy',
    'stay of proceedings',
    'motion for stay',
]

# Exclusions for bankruptcy - these mean bankruptcy is OVER, case should resume
BANKRUPTCY_EXCLUSIONS = [
    'resolved',
    'relief from',
    'relief of',
    'dismissal of bankruptcy',
    'reinstatement',
]

# Events that DISMISS/TERMINATE the case (case is closed)
DISMISSAL_EVENTS = [
    'dismissed',
    'voluntary dismissal',
    'order of dismissal',
    'case dismissed',
    'motion to dismiss',
]

# Exclusions for dismissal - these mean dismissal was DENIED
DISMISSAL_EXCLUSIONS = [
    'denying motion to dismiss',
    'denied motion to dismiss',
]

# Events indicating upset bid activity
UPSET_BID_EVENTS = [
    'upset bid filed',
    'upset bid',
    'notice of upset bid',
]

# Events indicating foreclosure process started (modern terminology)
FORECLOSURE_INITIATED_EVENTS = [
    'foreclosure case initiated',
    'petition for foreclosure',
    'notice of hearing',
    'findings and order of foreclosure',
    'foreclosure (special proceeding) notice of hearing',
]

# Exclusions for foreclosure initiated - these don't indicate initiation
FORECLOSURE_INITIATED_EXCLUSIONS = [
    'cancellation',
    'withdrawal',
    'canceled',
    'withdrawn',
]

# Events indicating foreclosure process started (older terminology)
# Used for cases from 2020-2022 that use different event names
# These require EXACT or STARTS WITH matching to avoid false positives
FORECLOSURE_INITIATED_LEGACY_EVENTS = [
    'petition',
    'cause of action',
    'other hearing',
]

# Exclusions for legacy events - party types and unrelated petitions
LEGACY_EXCLUSIONS = [
    'petitioner',  # Party type, not an event
    'petition to sell',
    'petition for commissions',
    'petition for partition',
    'petition for gal',
    'petition to proceed',
    'petition to enjoin',
    'bankruptcy petition',
]

# Combined list of all blocking events (for backward compatibility)
# Used by case_monitor to detect any event that stops/pauses the process
BLOCKING_EVENTS = BANKRUPTCY_EVENTS + DISMISSAL_EVENTS


# =============================================================================
# CLASSIFICATION FUNCTIONS
# =============================================================================

def get_case_events(case_id: int) -> List[CaseEvent]:
    """
    Get all events for a case ordered by date.

    Args:
        case_id: Database ID of the case

    Returns:
        List of CaseEvent objects ordered by event_date descending
    """
    with get_session() as session:
        events = session.query(CaseEvent).filter_by(case_id=case_id).order_by(
            CaseEvent.event_date.desc()
        ).all()
        # Detach from session so we can use them after session closes
        session.expunge_all()
        return events


def has_event_type(
    events: List[CaseEvent],
    event_types: List[str],
    exclusions: List[str] = None,
    strict_match: bool = False
) -> bool:
    """
    Check if any event matches the given types.

    Args:
        events: List of CaseEvent objects
        event_types: List of event type strings to match (case-insensitive)
        exclusions: List of strings that, if found, exclude the match
        strict_match: If True, event must START WITH the pattern (for legacy events)

    Returns:
        True if any event matches (and doesn't match exclusions)
    """
    event_types_lower = [et.lower() for et in event_types]
    exclusions_lower = [ex.lower() for ex in (exclusions or [])]

    for event in events:
        if event.event_type:
            event_type_lower = event.event_type.lower()

            # Check exclusions first - if any exclusion matches, skip this event
            if any(ex in event_type_lower for ex in exclusions_lower):
                continue

            for et in event_types_lower:
                if strict_match:
                    # Strict: event must start with or equal the pattern
                    if event_type_lower == et or event_type_lower.startswith(et + ' '):
                        return True
                else:
                    # Normal: pattern anywhere in event type
                    if et in event_type_lower:
                        return True

    return False


def get_latest_event_of_type(
    events: List[CaseEvent],
    event_types: List[str],
    exclusions: List[str] = None
) -> Optional[CaseEvent]:
    """
    Get the most recent event matching the given types.

    Args:
        events: List of CaseEvent objects (should be sorted by date desc)
        event_types: List of event type strings to match
        exclusions: List of strings that, if found, exclude the match

    Returns:
        Most recent matching CaseEvent or None
    """
    event_types_lower = [et.lower() for et in event_types]
    exclusions_lower = [ex.lower() for ex in (exclusions or [])]

    for event in events:
        if event.event_type:
            event_type_lower = event.event_type.lower()

            # Check exclusions first
            if any(ex in event_type_lower for ex in exclusions_lower):
                continue

            for et in event_types_lower:
                if et in event_type_lower:
                    return event

    return None


def is_foreclosure_case(case_id: int) -> bool:
    """Check if case type indicates this is a foreclosure case."""
    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if case and case.case_type:
            return 'foreclosure' in case.case_type.lower()
        return False


def classify_case(case_id: int) -> Optional[str]:
    """
    Classify a case into one of the defined states.

    Classification logic:
    1. If has dismissal event -> 'closed_dismissed'
    2. If has bankruptcy/stay event -> 'blocked'
    3. If has sale report AND within upset period -> 'upset_bid'
    4. If has sale report AND past upset period -> 'closed_sold'
    5. If foreclosure initiated (no sale yet) -> 'upcoming'
    6. If foreclosure case type + legacy events -> 'upcoming'
    7. Otherwise -> None

    Args:
        case_id: Database ID of the case

    Returns:
        'upcoming', 'upset_bid', 'blocked', 'closed_sold', 'closed_dismissed', or None
    """
    events = get_case_events(case_id)

    # Step 1: Check for dismissal (case terminated)
    # Excludes "denying motion to dismiss" which means case continues
    if has_event_type(events, DISMISSAL_EVENTS, exclusions=DISMISSAL_EXCLUSIONS):
        logger.debug(f"  Case {case_id}: Has dismissal event -> 'closed_dismissed'")
        return 'closed_dismissed'

    # Step 2: Check for bankruptcy/stay (case blocked, may resume)
    # Excludes "resolved", "relief from" which means bankruptcy is over
    if has_event_type(events, BANKRUPTCY_EVENTS, exclusions=BANKRUPTCY_EXCLUSIONS):
        logger.debug(f"  Case {case_id}: Has bankruptcy/stay -> 'blocked'")
        return 'blocked'

    # Step 3: Check for sale report
    sale_event = get_latest_event_of_type(events, SALE_REPORT_EVENTS)

    if sale_event:
        # Has sale report - check if within upset period
        # Get next_bid_deadline from database (populated by extractor)
        with get_session() as session:
            case = session.query(Case).filter_by(id=case_id).first()
            if case and case.next_bid_deadline:
                deadline = case.next_bid_deadline
                if datetime.now() <= deadline:
                    logger.debug(f"  Case {case_id}: Within upset period -> 'upset_bid'")
                    return 'upset_bid'
                else:
                    logger.debug(f"  Case {case_id}: Past upset deadline -> 'closed_sold'")
                    return 'closed_sold'

        # If no deadline in database, estimate from sale event date
        if sale_event.event_date:
            # NC upset bid period is 10 days from sale
            estimated_deadline = datetime.combine(
                sale_event.event_date + timedelta(days=10),
                datetime.min.time()
            )
            if datetime.now() <= estimated_deadline:
                logger.debug(f"  Case {case_id}: Estimated upset period -> 'upset_bid'")
                return 'upset_bid'
            else:
                logger.debug(f"  Case {case_id}: Past estimated deadline -> 'closed_sold'")
                return 'closed_sold'

        # Has sale but can't determine deadline - assume closed
        logger.debug(f"  Case {case_id}: Has sale, unknown deadline -> 'closed_sold'")
        return 'closed_sold'

    # Step 4: No sale yet - check if foreclosure has been initiated
    # Excludes "cancellation", "withdrawal" which don't indicate initiation
    if has_event_type(events, FORECLOSURE_INITIATED_EVENTS, exclusions=FORECLOSURE_INITIATED_EXCLUSIONS):
        logger.debug(f"  Case {case_id}: Foreclosure initiated, no sale -> 'upcoming'")
        return 'upcoming'

    # Step 5: Check for legacy event terminology (older cases)
    # Only if case_type confirms this is a foreclosure
    # Uses strict matching to avoid false positives like "Petitioner" (party type)
    if is_foreclosure_case(case_id):
        if has_event_type(
            events,
            FORECLOSURE_INITIATED_LEGACY_EVENTS,
            exclusions=LEGACY_EXCLUSIONS,
            strict_match=True
        ):
            logger.debug(f"  Case {case_id}: Legacy foreclosure events -> 'upcoming'")
            return 'upcoming'

    # Step 6: No foreclosure events at all
    logger.debug(f"  Case {case_id}: No foreclosure events")
    return None


def update_case_classification(case_id: int) -> Optional[str]:
    """
    Classify case and update the database.

    Args:
        case_id: Database ID of the case

    Returns:
        New classification value
    """
    try:
        classification = classify_case(case_id)

        with get_session() as session:
            case = session.query(Case).filter_by(id=case_id).first()
            if case:
                old_classification = case.classification
                case.classification = classification
                session.commit()

                if old_classification != classification:
                    logger.info(f"  Case {case_id}: {old_classification} -> {classification}")

                return classification

    except Exception as e:
        logger.error(f"  Error classifying case {case_id}: {e}")

    return None


def classify_all_cases(limit: int = None) -> dict:
    """
    Classify all cases in the database.

    Args:
        limit: Maximum number of cases to process

    Returns:
        Dict with counts for each classification state
    """
    results = {
        'upcoming': 0,
        'upset_bid': 0,
        'blocked': 0,
        'closed_sold': 0,
        'closed_dismissed': 0,
        'null': 0,
        'total': 0
    }

    with get_session() as session:
        query = session.query(Case.id)
        if limit:
            query = query.limit(limit)
        case_ids = [row[0] for row in query.all()]

    logger.info(f"Classifying {len(case_ids)} cases...")

    for case_id in case_ids:
        classification = update_case_classification(case_id)
        results['total'] += 1

        if classification in results:
            results[classification] += 1
        else:
            results['null'] += 1

    return results


def reclassify_stale_cases() -> int:
    """
    Re-classify cases that may have changed status due to time passing.

    For example, cases in 'upset_bid' status that are now past their deadline.

    Returns:
        Number of cases reclassified
    """
    reclassified = 0

    with get_session() as session:
        # Find upset_bid cases with passed deadlines
        now = datetime.now()
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid',
            Case.next_bid_deadline < now
        ).all()

        logger.info(f"Found {len(cases)} potentially stale upset_bid cases")

    for case in cases:
        old_class = case.classification
        new_class = update_case_classification(case.id)
        if old_class != new_class:
            reclassified += 1

    return reclassified
