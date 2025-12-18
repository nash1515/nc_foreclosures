"""API endpoints for AI analysis."""

from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy.orm.attributes import flag_modified

from common.logger import setup_logger
from database.connection import get_session
from database.models import Case, CaseAnalysis, Party
from web_app.auth.middleware import require_auth

logger = setup_logger(__name__)

analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/cases')


@analysis_bp.route('/<int:case_id>/analysis', methods=['GET'])
@require_auth
def get_analysis(case_id):
    """Get analysis results for a case."""
    with get_session() as session:
        analysis = session.query(CaseAnalysis).filter_by(case_id=case_id).first()

        if not analysis:
            return jsonify({'status': 'not_found', 'message': 'No analysis for this case'}), 404

        return jsonify({
            'status': analysis.status,
            'summary': analysis.summary,
            'financials': analysis.financials,
            'red_flags': analysis.red_flags or [],
            'discrepancies': analysis.discrepancies or [],
            'defendant_name': analysis.defendant_name,
            'deed_book': analysis.deed_book,
            'deed_page': analysis.deed_page,
            'document_contributions': analysis.document_contributions or [],
            'model_used': analysis.model_used,
            'input_tokens': analysis.input_tokens,
            'output_tokens': analysis.output_tokens,
            'cost_cents': analysis.cost_cents,
            'requested_at': analysis.requested_at.isoformat() if analysis.requested_at else None,
            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
            'error_message': analysis.error_message
        })


@analysis_bp.route('/<int:case_id>/analysis/discrepancies/<int:index>/resolve', methods=['POST'])
@require_auth
def resolve_discrepancy(case_id, index):
    """Resolve a discrepancy (accept or reject AI value)."""
    data = request.get_json()
    action = data.get('action')  # 'accept' or 'reject'

    if action not in ('accept', 'reject'):
        return jsonify({'error': 'action must be "accept" or "reject"'}), 400

    with get_session() as session:
        analysis = session.query(CaseAnalysis).filter_by(case_id=case_id).first()

        if not analysis:
            return jsonify({'error': 'No analysis for this case'}), 404

        discrepancies = analysis.discrepancies or []

        if index < 0 or index >= len(discrepancies):
            return jsonify({'error': 'Invalid discrepancy index'}), 400

        discrepancy = discrepancies[index]

        if discrepancy.get('status') != 'pending':
            return jsonify({'error': 'Discrepancy already resolved'}), 400

        # Update discrepancy status
        discrepancy['status'] = 'accepted' if action == 'accept' else 'rejected'
        discrepancy['resolved_at'] = datetime.now().isoformat()
        discrepancy['resolved_by'] = 'user'  # Could get actual user from session

        # If accepting, update the database field
        if action == 'accept':
            case = session.query(Case).filter_by(id=case_id).first()

            if not case:
                return jsonify({'error': 'Case not found'}), 404

            field = discrepancy['field']
            ai_value = discrepancy['ai_value']

            if field == 'property_address':
                case.property_address = ai_value
            elif field == 'current_bid_amount':
                case.current_bid_amount = float(ai_value)
            elif field == 'minimum_next_bid':
                case.minimum_next_bid = float(ai_value)
            elif field == 'defendant_name':
                # Add as new party if doesn't exist
                existing = session.query(Party).filter(
                    Party.case_id == case_id,
                    Party.party_name == ai_value
                ).first()
                if not existing:
                    new_party = Party(
                        case_id=case_id,
                        party_name=ai_value,
                        party_type='Defendant'
                    )
                    session.add(new_party)
            else:
                logger.warning(f"Unknown discrepancy field: {field} for case {case_id}")

            logger.info(f"Updated {field} for case {case_id} with AI value: {ai_value}")

        # Save updated discrepancies
        analysis.discrepancies = discrepancies
        flag_modified(analysis, 'discrepancies')
        session.commit()

        return jsonify({
            'success': True,
            'discrepancy': discrepancy
        })


@analysis_bp.route('/<int:case_id>/analysis/rerun', methods=['POST'])
@require_auth
def rerun_analysis(case_id):
    """Rerun analysis for a case (resets to pending)."""
    with get_session() as session:
        analysis = session.query(CaseAnalysis).filter_by(case_id=case_id).first()

        if not analysis:
            # Create new analysis record
            analysis = CaseAnalysis(case_id=case_id, status='pending')
            session.add(analysis)
        else:
            # Reset existing record
            analysis.status = 'pending'
            analysis.error_message = None
            analysis.requested_at = datetime.now()

        session.commit()

        return jsonify({'success': True, 'status': 'pending'})
