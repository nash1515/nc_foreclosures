"""Cases API endpoints."""

from flask import Blueprint, jsonify, request
from flask_dance.contrib.google import google
from sqlalchemy import or_
from database.connection import get_session
from database.models import Case, Party, Watchlist, User
from datetime import datetime

cases_bp = Blueprint('cases', __name__)

# Whitelist of allowed sort columns to prevent SQL injection
ALLOWED_SORT_COLUMNS = {
    'file_date', 'case_number', 'county_name', 'classification',
    'current_bid_amount', 'next_bid_deadline'
}


def get_current_user_id():
    """Get current user's ID from session."""
    if not google.authorized:
        return None

    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        return None

    email = resp.json().get('email')
    with get_session() as db_session:
        user = db_session.query(User).filter_by(email=email).first()
        return user.id if user else None


@cases_bp.route('', methods=['GET'])
def list_cases():
    """List cases with filters and pagination.

    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 20, max 100)
    - classification: Filter by classification (comma-separated for multiple)
    - county: Filter by county code (comma-separated for multiple)
    - search: Search case_number, property_address, or party names
    - start_date: Filter file_date >= start_date (YYYY-MM-DD)
    - end_date: Filter file_date <= end_date (YYYY-MM-DD)
    - watchlist_only: If 'true', only show watchlisted cases
    - sort_by: Column to sort by (default: file_date)
    - sort_order: 'asc' or 'desc' (default: desc)
    """
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()

    # Parse query params
    page = request.args.get('page', 1, type=int)
    page_size = min(request.args.get('page_size', 20, type=int), 100)
    classification = request.args.get('classification', '')
    county = request.args.get('county', '')
    search = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    watchlist_only = request.args.get('watchlist_only', 'false').lower() == 'true'
    sort_by = request.args.get('sort_by', 'file_date')
    sort_order = request.args.get('sort_order', 'desc')

    with get_session() as db_session:
        # Base query
        query = db_session.query(Case)

        # Classification filter
        if classification:
            classifications = [c.strip() for c in classification.split(',')]
            query = query.filter(Case.classification.in_(classifications))

        # County filter
        if county:
            counties = [c.strip() for c in county.split(',')]
            query = query.filter(Case.county_code.in_(counties))

        # Date range filter
        if start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Case.file_date >= start)
            except ValueError:
                pass

        if end_date:
            try:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Case.file_date <= end)
            except ValueError:
                pass

        # Search filter (case number, address, or party name)
        if search:
            search_pattern = f'%{search}%'
            # Subquery for party name search
            party_case_ids = db_session.query(Party.case_id).filter(
                Party.party_name.ilike(search_pattern)
            ).distinct()

            query = query.filter(
                or_(
                    Case.case_number.ilike(search_pattern),
                    Case.property_address.ilike(search_pattern),
                    Case.style.ilike(search_pattern),
                    Case.id.in_(party_case_ids)
                )
            )

        # Watchlist filter
        if watchlist_only:
            if not user_id:
                return jsonify({'error': 'User not found'}), 401
            watchlist_case_ids = db_session.query(Watchlist.case_id).filter(
                Watchlist.user_id == user_id
            )
            query = query.filter(Case.id.in_(watchlist_case_ids))

        # Get total count before pagination
        total = query.count()

        # Sorting - validate sort_by against whitelist
        if sort_by not in ALLOWED_SORT_COLUMNS:
            sort_by = 'file_date'
        sort_column = getattr(Case, sort_by)
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Pagination
        offset = (page - 1) * page_size
        cases = query.offset(offset).limit(page_size).all()

        # Get watchlist status for current user
        watchlist_case_ids = set()
        if user_id:
            watchlist_items = db_session.query(Watchlist.case_id).filter(
                Watchlist.user_id == user_id,
                Watchlist.case_id.in_([c.id for c in cases])
            ).all()
            watchlist_case_ids = {w.case_id for w in watchlist_items}

        # Serialize
        result = []
        for case in cases:
            result.append({
                'id': case.id,
                'case_number': case.case_number,
                'county_code': case.county_code,
                'county_name': case.county_name,
                'style': case.style,
                'classification': case.classification,
                'file_date': case.file_date.isoformat() if case.file_date else None,
                'property_address': case.property_address,
                'current_bid_amount': float(case.current_bid_amount) if case.current_bid_amount else None,
                'next_bid_deadline': case.next_bid_deadline.isoformat() if case.next_bid_deadline else None,
                'is_watchlisted': case.id in watchlist_case_ids
            })

        return jsonify({
            'cases': result,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        })


@cases_bp.route('/<int:case_id>', methods=['GET'])
def get_case(case_id):
    """Get full case detail including parties, events, and upset bidders."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()

    with get_session() as db_session:
        case = db_session.query(Case).filter_by(id=case_id).first()

        if not case:
            return jsonify({'error': 'Case not found'}), 404

        # Check if watchlisted
        is_watchlisted = False
        if user_id:
            watchlist = db_session.query(Watchlist).filter_by(
                user_id=user_id, case_id=case_id
            ).first()
            is_watchlisted = watchlist is not None

        # Get parties grouped by type
        parties = {}
        for party in case.parties:
            party_type = party.party_type
            if party_type not in parties:
                parties[party_type] = []
            parties[party_type].append(party.party_name)

        # Get events sorted by date (newest first)
        events = []
        for event in sorted(case.events, key=lambda e: e.event_date or datetime.min.date(), reverse=True):
            events.append({
                'id': event.id,
                'date': event.event_date.isoformat() if event.event_date else None,
                'type': event.event_type,
                'description': event.event_description,
                'filed_by': event.filed_by,
                'filed_against': event.filed_against,
                'document_url': event.document_url
            })

        # Get hearings
        hearings = []
        for hearing in case.hearings:
            hearings.append({
                'id': hearing.id,
                'date': hearing.hearing_date.isoformat() if hearing.hearing_date else None,
                'time': hearing.hearing_time,
                'type': hearing.hearing_type
            })

        # Extract upset bidders from events (events with "Upset Bid" type)
        upset_bidders = []
        for event in case.events:
            if event.event_type and 'upset' in event.event_type.lower():
                # Try to parse bidder info from description or filed_by
                upset_bidders.append({
                    'date': event.event_date.isoformat() if event.event_date else None,
                    'bidder': event.filed_by or 'Unknown',
                    'amount': None  # Amount would need to be parsed from description
                })

        return jsonify({
            'id': case.id,
            'case_number': case.case_number,
            'county_code': case.county_code,
            'county_name': case.county_name,
            'case_type': case.case_type,
            'case_status': case.case_status,
            'style': case.style,
            'classification': case.classification,
            'file_date': case.file_date.isoformat() if case.file_date else None,
            'case_url': case.case_url,
            'property_address': case.property_address,
            'current_bid_amount': float(case.current_bid_amount) if case.current_bid_amount else None,
            'minimum_next_bid': float(case.minimum_next_bid) if case.minimum_next_bid else None,
            'next_bid_deadline': case.next_bid_deadline.isoformat() if case.next_bid_deadline else None,
            'sale_date': case.sale_date.isoformat() if case.sale_date else None,
            'legal_description': case.legal_description,
            'trustee_name': case.trustee_name,
            'attorney_name': case.attorney_name,
            'attorney_phone': case.attorney_phone,
            'attorney_email': case.attorney_email,
            'parties': parties,
            'events': events,
            'hearings': hearings,
            'upset_bidders': upset_bidders,
            'is_watchlisted': is_watchlisted,
            'photo_url': None  # Placeholder for future enrichment
        })


@cases_bp.route('/<int:case_id>/watchlist', methods=['POST'])
def add_to_watchlist(case_id):
    """Add a case to user's watchlist."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    with get_session() as db_session:
        # Check if case exists
        case = db_session.query(Case).filter_by(id=case_id).first()
        if not case:
            return jsonify({'error': 'Case not found'}), 404

        # Check if already watchlisted
        existing = db_session.query(Watchlist).filter_by(
            user_id=user_id, case_id=case_id
        ).first()

        if existing:
            return jsonify({'message': 'Already in watchlist', 'is_watchlisted': True})

        # Add to watchlist
        watchlist = Watchlist(user_id=user_id, case_id=case_id)
        db_session.add(watchlist)
        db_session.commit()

        return jsonify({'message': 'Added to watchlist', 'is_watchlisted': True})


@cases_bp.route('/<int:case_id>/watchlist', methods=['DELETE'])
def remove_from_watchlist(case_id):
    """Remove a case from user's watchlist."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    with get_session() as db_session:
        watchlist = db_session.query(Watchlist).filter_by(
            user_id=user_id, case_id=case_id
        ).first()

        if watchlist:
            db_session.delete(watchlist)
            db_session.commit()

        return jsonify({'message': 'Removed from watchlist', 'is_watchlisted': False})
