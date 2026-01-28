"""Case status classification based on events and case type.

Classification states:
- 'upcoming': Foreclosure initiated, no sale report yet
- 'upset_bid': Has sale report AND within 10-day upset period
- 'blocked': Bankruptcy or stay in effect (check for updates during daily scrape)
- 'closed_sold': Sale completed, past upset period
- 'closed_dismissed': Case dismissed/terminated
"""

from datetime import datetime, timedelta, time
from typing import Optional, List
from threading import Thread

from database.connection import get_session
from database.models import Case, CaseEvent, Document, ClassificationHistory
from common.logger import setup_logger
from common.business_days import calculate_upset_bid_deadline

logger = setup_logger(__name__)


# =============================================================================
# ENRICHMENT TRIGGER
# =============================================================================

def _trigger_enrichment_async(case_id: int, case_number: str):
    """
    Trigger county-specific and PropWire enrichment in background thread.

    This is called when a case transitions to upset_bid status.
    The router determines which county enricher to use based on the case,
    and also runs PropWire enrichment for all counties.
    Runs asynchronously to avoid blocking the classification process.

    Args:
        case_id: Database ID of the case
        case_number: Case number for logging
    """
    try:
        # Import here to avoid circular dependency
        from enrichments import enrich_case
        logger.info(f"  Starting async enrichment for case {case_number}")
        result = enrich_case(case_id)

        # Log county RE enrichment result
        county_result = result.get('county_re', {})
        if county_result.get('success'):
            logger.info(f"  County RE enrichment succeeded for {case_number}: {county_result.get('url')}")
        elif county_result.get('skipped'):
            logger.debug(f"  County RE enrichment skipped for {case_number}: {county_result.get('error')}")
        elif county_result.get('review_needed'):
            logger.warning(f"  County RE enrichment needs review for {case_number}: {county_result.get('error')}")
        else:
            logger.error(f"  County RE enrichment failed for {case_number}: {county_result.get('error')}")

        # Log PropWire enrichment result
        propwire_result = result.get('propwire', {})
        if propwire_result.get('success'):
            logger.info(f"  PropWire enrichment succeeded for {case_number}: {propwire_result.get('url')}")
        elif propwire_result.get('review_needed'):
            logger.warning(f"  PropWire enrichment needs review for {case_number}: {propwire_result.get('error')}")
        else:
            logger.error(f"  PropWire enrichment failed for {case_number}: {propwire_result.get('error')}")
    except Exception as e:
        logger.error(f"  Async enrichment failed for case {case_number}: {e}")


def _trigger_vision_extraction_async(case_id: int, case_number: str):
    """
    Trigger Vision extraction sweep for all case documents in background thread.

    This is called when a case transitions to upset_bid status.
    Runs asynchronously to avoid blocking the classification process.

    Args:
        case_id: Database ID of the case
        case_number: Case number for logging
    """
    try:
        from ocr.vision_extraction import sweep_case_documents, update_case_from_vision_results

        logger.info(f"  Starting Vision sweep for case {case_number}")

        # Sweep all unprocessed documents
        sweep_result = sweep_case_documents(case_id)

        if sweep_result['documents_processed'] > 0:
            # Update case with extracted data
            update_case_from_vision_results(case_id, sweep_result['results'])
            logger.info(
                f"  Vision sweep complete for {case_number}: "
                f"{sweep_result['documents_processed']} docs, "
                f"${sweep_result['total_cost_cents']:.2f}"
            )
        else:
            logger.info(f"  Vision sweep: no documents to process for {case_number}")

        if sweep_result['errors']:
            for err in sweep_result['errors']:
                logger.warning(f"  Vision sweep warning: {err}")

    except Exception as e:
        logger.error(f"  Vision extraction failed for case {case_number}: {e}")


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

# Events indicating sale has been CONFIRMED by the court
# An "Order Confirming Sale" or "Confirmation of Sale" means the court has
# finalized the sale after the upset bid period passed with no valid bids.
# NOTE: This is used as ADDITIONAL confirmation, not sole indicator.
# Classification requires BOTH time-based check AND confirmation event.
# Variations include multiline portal display (e.g., "Order" + "of Confirmation of Sale")
# NOTE: Standalone "Confirmation" is included because in foreclosure context
# (when combined with sale report), it indicates sale confirmation
SALE_CONFIRMED_EVENTS = [
    'confirming sale',
    'confirmation of sale',
    'confirmation',  # Standalone - in foreclosure context means sale confirmation
    'order confirm sale',
    'order for confirmation',
    'order of confirmation',
    'order on confirmation',
    'order to confirm sale',
]

# Exclusions for sale confirmation - these indicate confirmation was reversed/rejected
SALE_CONFIRMED_EXCLUSIONS = [
    'set aside',
    'setting aside',
    'vacated',
    'denied',
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

# Exclusions for bankruptcy - when found IN SAME EVENT, means bankruptcy is over
BANKRUPTCY_EXCLUSIONS = [
    'resolved',
    'relief from',
    'relief of',
    'dismissal of bankruptcy',
    'reinstatement',
]

# Events that indicate bankruptcy/block has ENDED (separate events)
# If these appear AFTER a bankruptcy event, case is no longer blocked
BANKRUPTCY_LIFTED_EVENTS = [
    'order to reopen',
    'reopen',
    'reinstated',
    'case reopened',
    'notice of sale/resale',  # Resale notice implies block was lifted
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

# Events that indicate dismissal was REVERSED (case reopened after dismissal)
DISMISSAL_REVERSED_EVENTS = [
    'order to reopen',
    'reopen',
    'reinstated',
    'case reopened',
    'vacated',  # "Order Vacated" means previous order (like dismissal) was undone
]

# Events indicating upset bid activity
# Note: Pattern must NOT match "Upset Bidder" (party type, not an event)
UPSET_BID_EVENTS = [
    'upset bid filed',
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

# Events indicating the foreclosure has been finalized (case truly completed)
# These indicate all funds have been disbursed and the case is done
FINALIZATION_EVENTS = [
    'order confirming sale',
    'order of confirmation',
    'final report of sale',
    'commissioner\'s final report',
    'final account',
    'order for disbursement',
    'settlement statement',
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


def has_finalization_event(events: List[CaseEvent]) -> bool:
    """
    Check if any event indicates the case has been finalized.

    Finalization events indicate the case is truly complete - funds disbursed,
    all accounts settled, etc. These are stronger indicators than just
    "Order Confirming Sale" which happens after upset period.

    Args:
        events: List of CaseEvent objects

    Returns:
        True if any event matches finalization patterns
    """
    return has_event_type(events, FINALIZATION_EVENTS)


def get_finalization_event(events: List[CaseEvent]) -> Optional[CaseEvent]:
    """
    Get the most recent finalization event.

    Args:
        events: List of CaseEvent objects (should be sorted by date desc)

    Returns:
        Most recent finalization event or None
    """
    return get_latest_event_of_type(events, FINALIZATION_EVENTS)


def mark_case_finalized(case_id: int, event_id: int) -> bool:
    """
    Mark a case as finalized in the database.

    Sets is_finalized=True, finalized_at=now(), and finalized_event_id.

    Args:
        case_id: Database ID of the case
        event_id: Database ID of the finalization event

    Returns:
        True if successful, False otherwise
    """
    try:
        with get_session() as session:
            case = session.query(Case).filter_by(id=case_id).first()
            if case:
                case.is_finalized = True
                case.finalized_at = datetime.now()
                case.finalized_event_id = event_id
                session.commit()
                logger.info(f"  Case {case_id}: Marked as finalized (event_id={event_id})")
                return True
            else:
                logger.error(f"  Case {case_id}: Not found in database")
                return False
    except Exception as e:
        logger.error(f"  Error marking case {case_id} as finalized: {e}")
        return False


def is_foreclosure_case(case_id: int) -> bool:
    """Check if case type indicates this is a foreclosure case.

    NC foreclosures can have case_type:
    - "Foreclosure (Special Proceeding)" - explicit
    - "Special Proceeding" - older cases, but still foreclosures in this database
    """
    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if case and case.case_type:
            case_type_lower = case.case_type.lower()
            # Match explicit foreclosure case type
            if 'foreclosure' in case_type_lower:
                return True
            # NC foreclosures are often filed as "Special Proceeding"
            # All cases in this database are foreclosures (scraped from foreclosure portal)
            if case_type_lower == 'special proceeding':
                return True
        return False


def has_foreclosure_withdrawal(case_id: int, events: List[CaseEvent] = None) -> bool:
    """
    Check if case has a "Withdrawn" event indicating foreclosure withdrawal.

    A 'Withdrawn' event cancels the foreclosure. If it comes after a sale,
    it means the sale was withdrawn before the upset period completed.

    Since the sale isn't final until the 10-day upset period ends, a withdrawal
    during that period cancels everything.

    NOTE: This is different from "Withdrawal of Upset Bid" which is just
    a bidder withdrawing their bid - that doesn't affect case status.

    IMPORTANT: Chronology matters!
    - If there's a withdrawal but then a sale report AFTER the withdrawal,
      the case proceeded past the withdrawal -> not a foreclosure withdrawal
    - If there's a withdrawal AFTER a sale (during upset period), the sale
      was withdrawn before completion -> IS a foreclosure withdrawal

    The portal stores this as event_type = 'Withdrawn' in case_events.

    Args:
        case_id: Database ID of the case
        events: Optional list of events (to avoid re-querying)

    Returns:
        True if the most recent significant event is a withdrawal
    """
    # Get events if not provided
    if events is None:
        events = get_case_events(case_id)

    # Find most recent withdrawn event (excluding upset bid withdrawals)
    withdrawn_event = None
    for event in events:
        if event.event_type and 'withdrawn' in event.event_type.lower():
            # Skip "withdrawal of upset bid" - that's different
            if 'upset bid' in event.event_type.lower():
                continue
            # Use the most recent withdrawal (events are sorted desc)
            if withdrawn_event is None:
                withdrawn_event = event

    if not withdrawn_event or not withdrawn_event.event_date:
        return False

    # Get most recent sale report
    sale_event = get_latest_event_of_type(events, SALE_REPORT_EVENTS)

    # If no sale, or withdrawal is after most recent sale -> withdrawn
    if not sale_event or not sale_event.event_date:
        logger.debug(f"  Case {case_id}: Found foreclosure withdrawal event: {withdrawn_event.event_type} on {withdrawn_event.event_date} (no sale)")
        return True

    if withdrawn_event.event_date >= sale_event.event_date:
        logger.debug(f"  Case {case_id}: Withdrawal on {withdrawn_event.event_date} after/same as sale on {sale_event.event_date} -> foreclosure withdrawn")
        return True

    # Withdrawal before sale means it was withdrawn then restarted
    logger.debug(f"  Case {case_id}: Withdrawal on {withdrawn_event.event_date} superseded by sale on {sale_event.event_date}")
    return False


def get_most_recent_upset_bid_event(case_id: int) -> Optional[CaseEvent]:
    """Get the most recent 'Upset Bid Filed' event with a valid date.

    IMPORTANT: Only returns upset bids from the CURRENT sale cycle.
    If a sale was set aside and resold, upset bids from the old sale are ignored.
    This prevents using stale upset bid events to calculate deadlines.

    Args:
        case_id: Database ID of the case

    Returns:
        The most recent CaseEvent with type containing 'upset bid filed' and a valid date
        AFTER the most recent sale event, or None if no such event exists.
    """
    with get_session() as session:
        # First, get the most recent sale date to filter upset bids to current sale cycle
        case = session.query(Case).filter_by(id=case_id).first()
        sale_date = case.sale_date if case else None

        # If we have a sale_date, only consider upset bids AFTER that sale
        # This handles resales where old upset bids should be ignored
        query = session.query(CaseEvent).filter(
            CaseEvent.case_id == case_id,
            CaseEvent.event_type.ilike('%upset bid filed%'),
            CaseEvent.event_date.isnot(None)
        )

        if sale_date:
            # Only upset bids from current sale cycle (after the sale)
            query = query.filter(CaseEvent.event_date >= sale_date)

        event = query.order_by(CaseEvent.event_date.desc()).first()

        if event:
            # Detach from session before returning
            session.expunge(event)
        return event


def classify_case(case_id: int) -> Optional[str]:
    """
    Classify a case into one of the defined states.

    Classification logic (chronology-aware):
    1. If has foreclosure withdrawal document -> 'upcoming' (foreclosure may restart)
    2. If has dismissal event (and NOT later reversed/reopened) -> 'closed_dismissed'
    3. If has sale report:
       - If within upset period (sale date + 10 days, or latest upset bid + 10 days) -> 'upset_bid'
       - If past upset period -> 'closed_sold'
    4. If has bankruptcy/stay event (and NOT later lifted/reopened) -> 'blocked'
    5. If foreclosure initiated (no sale yet) -> 'upcoming'
    6. If foreclosure case type + legacy events -> 'upcoming'
    7. Otherwise -> None

    IMPORTANT: Chronology matters! Later events can supersede earlier ones:
    - Dismissal can be reversed by "Order to Reopen"
    - Bankruptcy can be lifted by "Order to Reopen"
    - Sale report takes priority over bankruptcy (case proceeded past bankruptcy)
    - Upset bids AFTER sale reset the 10-day deadline
    - Foreclosure withdrawal resets case to 'upcoming' (entire foreclosure withdrawn, may restart)

    Args:
        case_id: Database ID of the case

    Returns:
        'upcoming', 'upset_bid', 'blocked', 'closed_sold', 'closed_dismissed', or None
    """
    events = get_case_events(case_id)

    # Step 1: Check for foreclosure withdrawal FIRST
    # If the entire foreclosure was withdrawn, case returns to 'upcoming'
    # (foreclosure may be refiled/restarted)
    # NOTE: "Withdrawal of Upset Bid" is handled differently - see has_foreclosure_withdrawal()
    # IMPORTANT: Pass events to avoid re-querying and to check chronology
    if has_foreclosure_withdrawal(case_id, events):
        logger.debug(f"  Case {case_id}: Foreclosure withdrawn -> 'upcoming'")
        return 'upcoming'

    # Step 2: Check for dismissal (case terminated)
    # Excludes "denying motion to dismiss" which means case continues
    if has_event_type(events, DISMISSAL_EVENTS, exclusions=DISMISSAL_EXCLUSIONS):
        # Has dismissal - but check if it was later reversed/reopened
        dismissal_event = get_latest_event_of_type(events, DISMISSAL_EVENTS, exclusions=DISMISSAL_EXCLUSIONS)
        reversed_event = get_latest_event_of_type(events, DISMISSAL_REVERSED_EVENTS)

        # If there's a "reversed" event AFTER the dismissal, case is not closed
        if reversed_event and reversed_event.event_date and dismissal_event and dismissal_event.event_date:
            if reversed_event.event_date > dismissal_event.event_date:
                logger.debug(f"  Case {case_id}: Dismissal reversed on {reversed_event.event_date} (after {dismissal_event.event_date}) -> NOT dismissed")
            else:
                logger.debug(f"  Case {case_id}: Has dismissal event -> 'closed_dismissed'")
                return 'closed_dismissed'
        elif reversed_event:
            # Has reversed event but can't compare dates - assume not dismissed
            logger.debug(f"  Case {case_id}: Has dismissal but also reversed event -> NOT dismissed")
        else:
            # No reversed event - still dismissed
            logger.debug(f"  Case {case_id}: Has dismissal event -> 'closed_dismissed'")
            return 'closed_dismissed'

    # Step 3: Check for sale report FIRST (takes priority over bankruptcy)
    # A sale after bankruptcy means the case resumed and proceeded to sale
    sale_event = get_latest_event_of_type(events, SALE_REPORT_EVENTS)

    if sale_event:
        # RESALE DETECTION: Check if this is a new sale after a previous sale was set aside
        # If a case has a sale event NEWER than its stored sale_date,
        # the previous sale was set aside and this is a resale - reset the case
        # This can happen regardless of current classification (upset_bid, closed_sold, etc.)
        if sale_event.event_date:
            with get_session() as session:
                case = session.query(Case).filter_by(id=case_id).first()
                if case:
                    sale_event_date = sale_event.event_date.date() if hasattr(sale_event.event_date, 'date') else sale_event.event_date

                    # Determine baseline date: use stored sale_date, or find oldest sale event
                    baseline_date = case.sale_date

                    if not baseline_date:
                        # FALLBACK: No stored sale_date - find oldest "Report of Sale" event
                        # This handles cases where sale_date was never extracted from PDFs
                        all_sale_events = [e for e in events if e.event_type and
                                          any(kw in e.event_type.lower() for kw in ['report of sale', 'report of foreclosure sale'])]
                        if len(all_sale_events) > 1:
                            # Sort by event_date and use the oldest as baseline
                            all_sale_events.sort(key=lambda e: e.event_date if e.event_date else date.max)
                            oldest_sale = all_sale_events[0]
                            if oldest_sale.event_date:
                                baseline_date = oldest_sale.event_date.date() if hasattr(oldest_sale.event_date, 'date') else oldest_sale.event_date
                                logger.info(f"  Case {case_id}: No stored sale_date, using oldest sale event {baseline_date} as baseline")

                    if baseline_date and sale_event_date > baseline_date:
                        logger.info(f"  Case {case_id}: RESALE DETECTED - new sale {sale_event_date} after previous sale {baseline_date}")
                        # Reset the case for the new sale cycle
                        case.sale_date = sale_event_date
                        case.current_bid_amount = None  # Will be re-extracted from new Report of Sale
                        case.minimum_next_bid = None
                        case.next_bid_deadline = None
                        case.closed_sold_at = None  # Clear so grace period monitoring will pick it up if reclassified
                        session.commit()
                        logger.info(f"  Case {case_id}: Reset case data for resale, continuing to reclassify...")
                    elif not case.sale_date and sale_event_date:
                        # Populate missing sale_date from the sale event
                        case.sale_date = sale_event_date
                        session.commit()
                        logger.info(f"  Case {case_id}: Populated missing sale_date from event: {sale_event_date}")

        # SALE SET ASIDE CHECK: If the most recent sale was set aside, treat as no sale
        # This happens when a sale is voided and the case goes back to "upcoming" status
        sale_was_voided = False
        set_aside_events = [e for e in events if e.event_type and
                          any(kw in e.event_type.lower() for kw in ['set aside', 'setting aside', 'order to set aside'])]
        if set_aside_events and sale_event.event_date:
            sale_event_date = sale_event.event_date.date() if hasattr(sale_event.event_date, 'date') else sale_event.event_date
            # Check if any set aside event is AFTER the most recent sale
            for set_aside in set_aside_events:
                if set_aside.event_date:
                    set_aside_date = set_aside.event_date.date() if hasattr(set_aside.event_date, 'date') else set_aside.event_date
                    if set_aside_date > sale_event_date:
                        logger.info(f"  Case {case_id}: SALE SET ASIDE - {set_aside_date} after sale {sale_event_date}, treating as no sale")
                        # Clear sale data since the sale was voided
                        with get_session() as session:
                            case = session.query(Case).filter_by(id=case_id).first()
                            if case:
                                case.sale_date = None
                                case.current_bid_amount = None
                                case.minimum_next_bid = None
                                case.next_bid_deadline = None
                                case.closed_sold_at = None
                                session.commit()
                        # Skip the sale-based classification - will fall through to upcoming
                        sale_event = None
                        sale_was_voided = True
                        break

        # If sale was voided, skip remaining sale-based logic
        if sale_was_voided:
            logger.debug(f"  Case {case_id}: Sale voided, skipping to upcoming classification...")
            pass  # Fall through to Step 4 (bankruptcy) and Step 5 (upcoming)

        # Has sale report - check if within upset period
        # IMPORTANT: Each upset bid resets the 10-day period!
        # So we need to check the LATEST of: sale date, last upset bid date

        # FIRST: Check for recent upset bid events (regardless of stored deadline)
        # This ensures we catch newly filed upset bids even if stored deadline is stale
        recent_upset = get_most_recent_upset_bid_event(case_id)
        if recent_upset and recent_upset.event_date:
            event_deadline = calculate_upset_bid_deadline(recent_upset.event_date)
            if datetime.now().date() <= event_deadline:
                logger.debug(f"  Case {case_id}: Recent upset bid event on {recent_upset.event_date} -> 'upset_bid' (deadline: {event_deadline})")
                return 'upset_bid'

        # THEN: Fall back to stored deadline if no recent events or deadline passed
        with get_session() as session:
            case = session.query(Case).filter_by(id=case_id).first()
            if case and case.next_bid_deadline:
                deadline = case.next_bid_deadline
                if datetime.now() <= deadline:
                    logger.debug(f"  Case {case_id}: Within upset period (DB deadline) -> 'upset_bid'")
                    return 'upset_bid'

        # Check for upset bid events - each one resets the 10-day period
        latest_upset_bid = get_latest_event_of_type(events, UPSET_BID_EVENTS)

        # Determine the reference date for deadline calculation
        # Use the LATEST of: sale date, last upset bid date
        # Only use upset bid if it's AFTER the sale (upset bids before sale are from previous sale cycle)
        reference_date = None
        reference_source = None

        if sale_event and sale_event.event_date:
            reference_date = sale_event.event_date
            reference_source = "sale"

            # Check if there's an upset bid AFTER the sale - that resets the 10-day period
            if latest_upset_bid and latest_upset_bid.event_date:
                if latest_upset_bid.event_date > sale_event.event_date:
                    reference_date = latest_upset_bid.event_date
                    reference_source = "upset bid"

        if reference_date:
            # NC upset bid period is 10 days from the reference event (adjusted for weekends/holidays)
            adjusted_deadline = calculate_upset_bid_deadline(reference_date)
            # Use end-of-day (5 PM courthouse close) - deadline is the ENTIRE day, not midnight
            estimated_deadline = datetime.combine(adjusted_deadline, time(17, 0, 0))
            if datetime.now() <= estimated_deadline:
                logger.debug(f"  Case {case_id}: Within upset period (from {reference_source} on {reference_date}, deadline {adjusted_deadline}) -> 'upset_bid'")
                return 'upset_bid'
            else:
                # Past deadline - but first check if a blocking event interrupted the upset period
                # If bankruptcy/stay was filed DURING the upset period, the sale never completed
                blocking_event = get_latest_event_of_type(events, BANKRUPTCY_EVENTS, exclusions=BANKRUPTCY_EXCLUSIONS)
                if blocking_event and blocking_event.event_date:
                    block_date = blocking_event.event_date.date() if hasattr(blocking_event.event_date, 'date') else blocking_event.event_date
                    ref_date = reference_date.date() if hasattr(reference_date, 'date') else reference_date
                    # Was the block during the upset period? (after reference_date, before/on deadline)
                    if ref_date < block_date <= adjusted_deadline:
                        # Block interrupted the upset period - sale never completed
                        lifted_event = get_latest_event_of_type(events, BANKRUPTCY_LIFTED_EVENTS)
                        if lifted_event and lifted_event.event_date:
                            lift_date = lifted_event.event_date.date() if hasattr(lifted_event.event_date, 'date') else lifted_event.event_date
                            if lift_date > block_date:
                                # Block was lifted - case is upcoming (awaiting resale)
                                logger.info(f"  Case {case_id}: Block during upset period ({block_date}) was lifted ({lift_date}) -> 'upcoming'")
                                return 'upcoming'
                        # Block still active
                        logger.info(f"  Case {case_id}: Block during upset period ({block_date}), not lifted -> 'blocked'")
                        return 'blocked'

                # No blocking event during upset period - proceed with closed_sold logic
                # Defense in depth: require BOTH time passed AND confirmation event
                has_confirmation = has_event_type(
                    events, SALE_CONFIRMED_EVENTS, exclusions=SALE_CONFIRMED_EXCLUSIONS
                )
                if has_confirmation:
                    logger.debug(f"  Case {case_id}: Past deadline + has confirmation event -> 'closed_sold' (high confidence)")
                else:
                    logger.debug(f"  Case {case_id}: Past deadline (from {reference_source} on {reference_date}, deadline {adjusted_deadline}) -> 'closed_sold'")
                if not sale_was_voided:
                    return 'closed_sold'

        # Has sale but can't determine deadline - check for confirmation event
        # If we have both a sale AND a confirmation, it's definitely closed
        has_confirmation = has_event_type(
            events, SALE_CONFIRMED_EVENTS, exclusions=SALE_CONFIRMED_EXCLUSIONS
        )
        if has_confirmation and not sale_was_voided:
            logger.debug(f"  Case {case_id}: Has sale + confirmation event, unknown deadline -> 'closed_sold'")
            return 'closed_sold'

        # Has sale but no confirmation and no deadline - assume closed (legacy behavior)
        if not sale_was_voided:
            logger.debug(f"  Case {case_id}: Has sale, unknown deadline, no confirmation -> 'closed_sold'")
            return 'closed_sold'

    # Step 4: No sale yet - check for bankruptcy/stay (case blocked, may resume)
    # Only check bankruptcy if there's no sale - a sale means case proceeded past bankruptcy
    if has_event_type(events, BANKRUPTCY_EVENTS, exclusions=BANKRUPTCY_EXCLUSIONS):
        # Has bankruptcy - but check if it was later lifted (e.g., "Order to Reopen")
        bankruptcy_event = get_latest_event_of_type(events, BANKRUPTCY_EVENTS, exclusions=BANKRUPTCY_EXCLUSIONS)
        lifted_event = get_latest_event_of_type(events, BANKRUPTCY_LIFTED_EVENTS)

        # If there's a "lifted" event AFTER the bankruptcy event, case is not blocked
        if lifted_event and lifted_event.event_date and bankruptcy_event and bankruptcy_event.event_date:
            if lifted_event.event_date > bankruptcy_event.event_date:
                logger.debug(f"  Case {case_id}: Bankruptcy lifted on {lifted_event.event_date} (after {bankruptcy_event.event_date}) -> NOT blocked")
            else:
                logger.debug(f"  Case {case_id}: Has bankruptcy/stay (no sale) -> 'blocked'")
                return 'blocked'
        elif lifted_event:
            # Has lifted event but can't compare dates - assume not blocked
            logger.debug(f"  Case {case_id}: Has bankruptcy but also lifted event -> NOT blocked")
        else:
            # No lifted event - still blocked
            logger.debug(f"  Case {case_id}: Has bankruptcy/stay (no sale) -> 'blocked'")
            return 'blocked'

    # Step 5: No sale yet - check if foreclosure has been initiated
    # Excludes "cancellation", "withdrawal" which don't indicate initiation
    if has_event_type(events, FORECLOSURE_INITIATED_EVENTS, exclusions=FORECLOSURE_INITIATED_EXCLUSIONS):
        logger.debug(f"  Case {case_id}: Foreclosure initiated, no sale -> 'upcoming'")
        return 'upcoming'

    # Step 6: Check for legacy event terminology (older cases)
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

    # Step 7: No foreclosure events at all
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

                # Track when case transitions to closed_sold for grace period monitoring
                if classification == 'closed_sold' and old_classification != 'closed_sold':
                    case.closed_sold_at = datetime.now()
                    logger.debug(f"  Case {case_id}: Set closed_sold_at timestamp")
                elif classification != 'closed_sold' and old_classification == 'closed_sold':
                    case.closed_sold_at = None
                    logger.debug(f"  Case {case_id}: Cleared closed_sold_at timestamp")

                # Ensure upset_bid cases have a valid deadline
                # This handles: 1) missing deadline, 2) stale deadline from previous sale cycle
                if classification == 'upset_bid' and case.sale_date:
                    deadline_missing = not case.next_bid_deadline
                    deadline_stale = case.next_bid_deadline and case.next_bid_deadline.date() < case.sale_date

                    if deadline_missing or deadline_stale:
                        # Find most recent upset bid in current sale cycle (query within this session)
                        recent_upset = session.query(CaseEvent).filter(
                            CaseEvent.case_id == case_id,
                            CaseEvent.event_type.ilike('%upset bid filed%'),
                            CaseEvent.event_date.isnot(None),
                            CaseEvent.event_date >= case.sale_date
                        ).order_by(CaseEvent.event_date.desc()).first()

                        if recent_upset and recent_upset.event_date:
                            # Calculate from most recent upset bid
                            adjusted_deadline = calculate_upset_bid_deadline(recent_upset.event_date)
                            source = f"upset bid on {recent_upset.event_date}"
                        else:
                            # No upset bids yet, calculate from sale date
                            adjusted_deadline = calculate_upset_bid_deadline(case.sale_date)
                            source = f"sale date {case.sale_date}"

                        old_deadline = case.next_bid_deadline.date() if case.next_bid_deadline else None
                        case.next_bid_deadline = datetime.combine(adjusted_deadline, datetime.min.time())

                        if deadline_stale:
                            logger.warning(f"  Case {case_id}: Fixed stale deadline {old_deadline} -> {adjusted_deadline} (from {source})")
                        else:
                            logger.info(f"  Case {case_id}: Set deadline to {adjusted_deadline} from {source}")

                # Log classification change if it occurred
                if old_classification != classification:
                    history = ClassificationHistory(
                        case_id=case_id,
                        old_classification=old_classification,
                        new_classification=classification,
                        trigger='scrape'
                    )
                    session.add(history)

                session.commit()

                if old_classification != classification:
                    logger.info(f"  Case {case_id}: {old_classification} -> {classification}")

                    # Trigger async enrichment when case becomes upset_bid (router handles county)
                    if classification == 'upset_bid':
                        Thread(
                            target=_trigger_enrichment_async,
                            args=(case.id, case.case_number),
                            daemon=True
                        ).start()
                        logger.info(f"  Case {case.case_number}: Queued enrichment")

                        # Trigger Vision extraction sweep
                        Thread(
                            target=_trigger_vision_extraction_async,
                            args=(case.id, case.case_number),
                            daemon=True
                        ).start()
                        logger.info(f"  Case {case.case_number}: Queued Vision extraction")

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

    IMPORTANT: Before reclassifying, checks for recent upset bid events that
    would extend the deadline. Updates the deadline if a recent upset bid is found.

    Returns:
        Number of cases reclassified
    """
    reclassified = 0

    with get_session() as session:
        # Find upset_bid cases with passed deadlines
        now = datetime.now()
        case_data = session.query(Case.id, Case.classification).filter(
            Case.classification == 'upset_bid',
            Case.next_bid_deadline < now
        ).all()

        logger.info(f"Found {len(case_data)} potentially stale upset_bid cases")

    for case_id, old_class in case_data:
        # CHECK for recent upset bids before reclassifying
        recent_upset = get_most_recent_upset_bid_event(case_id)
        if recent_upset and recent_upset.event_date:
            new_deadline = calculate_upset_bid_deadline(recent_upset.event_date)
            if datetime.now().date() <= new_deadline:
                # Update deadline instead of reclassifying
                with get_session() as session:
                    case = session.query(Case).filter_by(id=case_id).first()
                    if case:
                        case.next_bid_deadline = datetime.combine(new_deadline, datetime.min.time())
                        session.commit()
                        logger.info(f"  Case {case_id}: Updated deadline to {new_deadline} (recent upset bid on {recent_upset.event_date})")
                continue

        # No recent upset bids - safe to reclassify
        new_class = update_case_classification(case_id)
        if old_class != new_class:
            reclassified += 1

    return reclassified
