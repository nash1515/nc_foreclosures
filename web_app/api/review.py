"""Review Queue API endpoints."""

import json
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import func

from database.connection import get_session
from database.models import Case, CaseEvent, Party, Hearing, SkippedCase
from common.logger import setup_logger
from web_app.auth.middleware import require_auth

logger = setup_logger(__name__)

review_bp = Blueprint('review', __name__)


@review_bp.route('/daily', methods=['GET'])
@require_auth
def get_daily_review():
    """
    Get cases for daily review.

    Query params:
        date: YYYY-MM-DD (default: today)

    Returns:
        {
            "date": "2025-12-04",
            "foreclosures": [...],
            "skipped": [...],
            "counts": {"foreclosures": N, "skipped": M}
        }
    """
    date_str = request.args.get('date')

    if date_str:
        try:
            review_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    else:
        review_date = date.today()

    with get_session() as session:
        # Get foreclosures added on this date (exclude already reviewed)
        foreclosures = session.query(Case).filter(
            func.date(Case.created_at) == review_date,
            Case.reviewed_at.is_(None)
        ).all()

        foreclosure_list = []
        for case in foreclosures:
            # Get events for this case
            events = session.query(CaseEvent).filter_by(case_id=case.id).all()
            event_list = [
                {
                    'event_date': e.event_date.strftime('%Y-%m-%d') if e.event_date else None,
                    'event_type': e.event_type,
                    'document_url': e.document_url
                }
                for e in events
            ]

            foreclosure_list.append({
                'id': case.id,
                'case_number': case.case_number,
                'county_name': case.county_name,
                'case_type': case.case_type,
                'style': case.style,
                'file_date': case.file_date.strftime('%Y-%m-%d') if case.file_date else None,
                'case_url': case.case_url,
                'classification': case.classification,
                'events': event_list
            })

        # Get pending skipped cases from last 7 days (daily scrapes only, not historical backfill)
        seven_days_ago = review_date - timedelta(days=7)
        skipped = session.query(SkippedCase).filter(
            SkippedCase.review_action.is_(None),  # Only pending review
            SkippedCase.scrape_date >= seven_days_ago  # Only recent daily scrapes
        ).all()

        skipped_list = []
        for case in skipped:
            events = case.events_json if case.events_json else []
            skipped_list.append({
                'id': case.id,
                'case_number': case.case_number,
                'county_name': case.county_name,
                'case_type': case.case_type,
                'style': case.style,
                'file_date': case.file_date.strftime('%Y-%m-%d') if case.file_date else None,
                'case_url': case.case_url,
                'skip_reason': case.skip_reason,
                'events': events
            })

        return jsonify({
            'date': review_date.strftime('%Y-%m-%d'),
            'foreclosures': foreclosure_list,
            'skipped': skipped_list,
            'counts': {
                'foreclosures': len(foreclosure_list),
                'skipped': len(skipped_list),
                'pending_review': len(foreclosure_list) + len(skipped_list)
            }
        })


@review_bp.route('/foreclosures/approve-all', methods=['POST'])
@require_auth
def approve_all_foreclosures():
    """
    Mark all foreclosures for a date as reviewed (approved).

    Body:
        {"date": "2025-12-08"}
    """
    data = request.get_json() or {}
    date_str = data.get('date')

    if not date_str:
        return jsonify({'error': 'No date provided'}), 400

    try:
        review_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    with get_session() as session:
        # Get all unreviewed foreclosures for this date
        foreclosures = session.query(Case).filter(
            func.date(Case.created_at) == review_date,
            Case.reviewed_at.is_(None)
        ).all()

        approved = 0
        for case in foreclosures:
            case.reviewed_at = datetime.utcnow()
            approved += 1

        session.commit()

        logger.info(f"Approved all {approved} foreclosures for {date_str}")

        return jsonify({
            'success': True,
            'approved': approved
        })


@review_bp.route('/foreclosures/approve', methods=['POST'])
@require_auth
def approve_foreclosures():
    """
    Mark specific foreclosures as reviewed (approved) by case IDs.

    Body:
        {"case_ids": [1, 2, 3]}
    """
    data = request.get_json() or {}
    case_ids = data.get('case_ids', [])

    if not case_ids:
        return jsonify({'error': 'No case IDs provided'}), 400

    with get_session() as session:
        approved = 0
        for case_id in case_ids:
            case = session.query(Case).get(case_id)
            if case and case.reviewed_at is None:
                case.reviewed_at = datetime.utcnow()
                approved += 1

        session.commit()

        logger.info(f"Approved {approved} foreclosures by ID")

        return jsonify({
            'success': True,
            'approved': approved
        })


@review_bp.route('/foreclosures/reject', methods=['POST'])
@require_auth
def reject_foreclosures():
    """
    Reject (delete) foreclosure cases.

    Body:
        {"case_ids": [1, 2, 3]}
    """
    data = request.get_json()
    case_ids = data.get('case_ids', [])

    if not case_ids:
        return jsonify({'error': 'No case_ids provided'}), 400

    with get_session() as session:
        deleted = 0
        for case_id in case_ids:
            case = session.query(Case).filter_by(id=case_id).first()
            if case:
                session.delete(case)
                deleted += 1
                logger.info(f"Rejected (deleted) case {case.case_number}")

        session.commit()

        return jsonify({
            'success': True,
            'deleted': deleted
        })


@review_bp.route('/skipped/add', methods=['POST'])
@require_auth
def add_skipped_cases():
    """
    Add skipped cases as foreclosures.

    Body:
        {"skipped_ids": [1, 2, 3]}

    This fetches fresh data from the portal and saves to cases table.
    """
    data = request.get_json()
    skipped_ids = data.get('skipped_ids', [])

    if not skipped_ids:
        return jsonify({'error': 'No skipped_ids provided'}), 400

    with get_session() as session:
        added = 0
        errors = []

        for skipped_id in skipped_ids:
            skipped = session.query(SkippedCase).filter_by(id=skipped_id).first()
            if not skipped:
                errors.append(f"Skipped case {skipped_id} not found")
                continue

            # Check if case already exists
            existing = session.query(Case).filter_by(case_number=skipped.case_number).first()
            if existing:
                # Mark as reviewed (already exists)
                skipped.reviewed_at = datetime.utcnow()
                skipped.review_action = 'added'
                logger.info(f"Case {skipped.case_number} already exists, marking as reviewed")
                continue

            # Create case from skipped data
            case = Case(
                case_number=skipped.case_number,
                county_code=skipped.county_code,
                county_name=skipped.county_name,
                case_type=skipped.case_type,
                case_status=None,
                file_date=skipped.file_date,
                style=skipped.style,
                case_url=skipped.case_url,
                classification='upcoming'  # Default to upcoming
            )
            session.add(case)
            session.flush()

            # Add events from JSON (handle double-encoded JSON from scraper)
            events_raw = skipped.events_json if skipped.events_json else []
            # If it's a string (double-encoded), parse it
            if isinstance(events_raw, str):
                try:
                    events = json.loads(events_raw)
                except json.JSONDecodeError:
                    events = []
            else:
                events = events_raw if events_raw else []

            for event_data in events:
                event = CaseEvent(
                    case_id=case.id,
                    event_date=event_data.get('event_date'),
                    event_type=event_data.get('event_type')
                )
                session.add(event)

            # Mark skipped case as reviewed
            skipped.reviewed_at = datetime.utcnow()
            skipped.review_action = 'added'

            added += 1
            logger.info(f"Added skipped case {skipped.case_number} as foreclosure")

        session.commit()

        return jsonify({
            'success': True,
            'added': added,
            'errors': errors
        })


@review_bp.route('/skipped/dismiss', methods=['POST'])
@require_auth
def dismiss_skipped_cases():
    """
    Dismiss skipped cases (confirm they are not foreclosures).

    Body:
        {"skipped_ids": [1, 2, 3]}
    """
    data = request.get_json()
    skipped_ids = data.get('skipped_ids', [])

    if not skipped_ids:
        return jsonify({'error': 'No skipped_ids provided'}), 400

    with get_session() as session:
        dismissed = 0
        for skipped_id in skipped_ids:
            skipped = session.query(SkippedCase).filter_by(id=skipped_id).first()
            if skipped:
                skipped.reviewed_at = datetime.utcnow()
                skipped.review_action = 'dismissed'
                dismissed += 1
                logger.info(f"Dismissed skipped case {skipped.case_number}")

        session.commit()

        return jsonify({
            'success': True,
            'dismissed': dismissed
        })


@review_bp.route('/cleanup', methods=['DELETE'])
@require_auth
def cleanup_old_skipped():
    """
    Remove old dismissed skipped cases.

    Query params:
        days: Number of days to keep (default: 7)
    """
    days = request.args.get('days', 7, type=int)
    cutoff = date.today() - timedelta(days=days)

    with get_session() as session:
        # Delete dismissed skipped cases older than cutoff
        deleted = session.query(SkippedCase).filter(
            SkippedCase.review_action == 'dismissed',
            SkippedCase.scrape_date < cutoff
        ).delete()

        session.commit()

        logger.info(f"Cleaned up {deleted} old dismissed skipped cases")

        return jsonify({
            'success': True,
            'deleted': deleted
        })


@review_bp.route('/pending-count', methods=['GET'])
@require_auth
def get_pending_count():
    """Get count of cases pending review (for badge)."""
    with get_session() as session:
        # Count today's unreviewed foreclosures
        today = date.today()
        foreclosure_count = session.query(Case).filter(
            func.date(Case.created_at) == today,
            Case.reviewed_at.is_(None)
        ).count()

        # Count pending skipped cases from last 7 days (daily scrapes only)
        seven_days_ago = today - timedelta(days=7)
        skipped_count = session.query(SkippedCase).filter(
            SkippedCase.review_action.is_(None),
            SkippedCase.scrape_date >= seven_days_ago
        ).count()

        return jsonify({
            'foreclosures': foreclosure_count,
            'skipped': skipped_count,
            'total': foreclosure_count + skipped_count
        })
