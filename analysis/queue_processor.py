# analysis/queue_processor.py
"""Process pending AI analysis queue."""

from typing import Dict, Any, List
from datetime import datetime

from common.logger import setup_logger
from database.connection import get_session
from database.models import CaseAnalysis
from analysis.analyzer import analyze_case

logger = setup_logger(__name__)


def process_analysis_queue(max_items: int = 10) -> Dict[str, Any]:
    """
    Process pending analyses from the queue.

    Args:
        max_items: Maximum number of analyses to process in one run

    Returns:
        Dict with processing results
    """
    logger.info("Starting analysis queue processing")

    results = {
        'processed': 0,
        'succeeded': 0,
        'failed': 0,
        'details': []
    }

    with get_session() as session:
        # Get pending analyses ordered by request time
        pending = session.query(CaseAnalysis).filter(
            CaseAnalysis.status == 'pending'
        ).order_by(
            CaseAnalysis.requested_at
        ).limit(max_items).all()

        if not pending:
            logger.info("No pending analyses found")
            return results

        logger.info(f"Found {len(pending)} pending analyses")

    # Process each analysis (outside session to avoid long transactions)
    for analysis in pending:
        case_id = analysis.case_id
        result = analyze_case(case_id)

        results['processed'] += 1
        if result.get('status') == 'completed':
            results['succeeded'] += 1
        else:
            results['failed'] += 1

        results['details'].append({
            'case_id': case_id,
            'status': result.get('status', 'failed'),
            'error': result.get('error'),
            'cost_cents': result.get('cost_cents', 0)
        })

    logger.info(f"Queue processing complete: {results['succeeded']}/{results['processed']} succeeded")
    return results


def enqueue_analysis(case_id: int) -> bool:
    """
    Add a case to the analysis queue.

    Args:
        case_id: The case ID to queue for analysis

    Returns:
        True if queued successfully, False if already queued
    """
    with get_session() as session:
        # Check if already queued
        existing = session.query(CaseAnalysis).filter_by(case_id=case_id).first()
        if existing:
            logger.debug(f"Case {case_id} already has analysis record (status={existing.status})")
            return False

        # Create new analysis record
        analysis = CaseAnalysis(
            case_id=case_id,
            status='pending',
            requested_at=datetime.now()
        )
        session.add(analysis)
        session.commit()

        logger.info(f"Queued case {case_id} for AI analysis")
        return True


def get_queue_status() -> Dict[str, Any]:
    """Get current queue status."""
    with get_session() as session:
        pending = session.query(CaseAnalysis).filter_by(status='pending').count()
        processing = session.query(CaseAnalysis).filter_by(status='processing').count()
        completed = session.query(CaseAnalysis).filter_by(status='completed').count()
        failed = session.query(CaseAnalysis).filter_by(status='failed').count()

        return {
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'failed': failed,
            'total': pending + processing + completed + failed
        }
