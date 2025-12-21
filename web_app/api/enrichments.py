"""API endpoints for enrichment operations."""

import logging
from flask import Blueprint, jsonify, request, g

from database.connection import get_session
from database.models import Case
from web_app.auth.middleware import require_auth
from enrichments.common.models import Enrichment, EnrichmentReviewLog
from enrichments.wake_re import enrich_case as enrich_wake_re
from enrichments.wake_re.url_builder import build_account_url


logger = logging.getLogger(__name__)

bp = Blueprint('enrichments', __name__)


@bp.route('/api/enrichments/wake-re/<int:case_id>', methods=['POST'])
@require_auth
def trigger_wake_re_enrichment(case_id):
    """
    Manually trigger Wake RE enrichment for a case.

    Use cases:
        - Retry failed enrichments
        - Enrich historical cases
        - On-demand enrichment
    """
    try:
        result = enrich_wake_re(case_id)
        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code
    except Exception as e:
        logger.exception(f"Error enriching case {case_id}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/enrichments/review-queue', methods=['GET'])
@require_auth
def get_review_queue():
    """
    Fetch unresolved enrichment review items.

    Query params:
        - enrichment_type: Filter by type (e.g., 'wake_re')
        - limit: Max results (default 50)
    """
    enrichment_type = request.args.get('enrichment_type')
    limit = request.args.get('limit', 50, type=int)

    with get_session() as session:
        query = session.query(EnrichmentReviewLog).filter(
            EnrichmentReviewLog.resolved_at.is_(None)
        ).order_by(EnrichmentReviewLog.created_at.desc())

        if enrichment_type:
            query = query.filter(EnrichmentReviewLog.enrichment_type == enrichment_type)

        logs = query.limit(limit).all()

        results = []
        for log in logs:
            case = session.query(Case).filter_by(id=log.case_id).first()
            results.append({
                'id': log.id,
                'case_id': log.case_id,
                'case_number': case.case_number if case else None,
                'enrichment_type': log.enrichment_type,
                'search_method': log.search_method,
                'search_value': log.search_value,
                'matches_found': log.matches_found,
                'raw_results': log.raw_results,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            })

        return jsonify(results)


@bp.route('/api/enrichments/resolve/<int:log_id>', methods=['POST'])
@require_auth
def resolve_review_item(log_id):
    """
    Resolve an enrichment review item.

    Body:
        {
            'account_id': '0379481',  # Selected account (if manual resolution)
            'notes': 'Admin notes...'
        }
    """
    with get_session() as session:
        log = session.query(EnrichmentReviewLog).filter_by(id=log_id).first()
        if not log:
            return jsonify({'error': 'Review item not found'}), 404

        if log.resolved_at:
            return jsonify({'error': 'Already resolved'}), 400

        data = request.get_json() or {}
        account_id = data.get('account_id')
        notes = data.get('notes', '')

        # Mark as resolved
        from datetime import datetime
        log.resolved_at = datetime.now()
        log.resolved_by = g.user.id if hasattr(g, 'user') and g.user else None
        log.resolution_notes = notes

        url = None
        # If account_id provided, save the enrichment
        if account_id and log.enrichment_type == 'wake_re':
            url = build_account_url(account_id)

            enrichment = session.query(Enrichment).filter_by(case_id=log.case_id).first()
            if not enrichment:
                enrichment = Enrichment(case_id=log.case_id)
                session.add(enrichment)

            enrichment.wake_re_account = account_id
            enrichment.wake_re_url = url
            enrichment.wake_re_enriched_at = datetime.now()
            enrichment.wake_re_error = None

        return jsonify({
            'success': True,
            'message': f'Resolved review item {log_id}',
            'url': url if account_id else None,
        })


@bp.route('/api/enrichments/status/<int:case_id>', methods=['GET'])
@require_auth
def get_enrichment_status(case_id):
    """Get enrichment status for a case."""
    with get_session() as session:
        enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()

        if not enrichment:
            return jsonify({
                'case_id': case_id,
                'wake_re': None,
            })

        return jsonify({
            'case_id': case_id,
            'wake_re': {
                'url': enrichment.wake_re_url,
                'account': enrichment.wake_re_account,
                'enriched_at': enrichment.wake_re_enriched_at.isoformat() if enrichment.wake_re_enriched_at else None,
                'error': enrichment.wake_re_error,
            },
        })
