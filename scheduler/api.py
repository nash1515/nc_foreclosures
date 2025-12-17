"""API endpoints for scheduler configuration.

These endpoints allow the frontend to:
- View current schedule settings
- Update schedule (time, days, enabled/disabled)
- View job history and status
- Trigger immediate runs
"""

from datetime import datetime
from flask import Blueprint, jsonify, request

from database.connection import get_session
from database.models import SchedulerConfig, ScrapeLog, ScrapeLogTask

scheduler_api = Blueprint('scheduler', __name__, url_prefix='/api/scheduler')


@scheduler_api.route('/config', methods=['GET'])
def get_scheduler_config():
    """Get all scheduler job configurations."""
    with get_session() as session:
        configs = session.query(SchedulerConfig).all()
        return jsonify({
            'jobs': [{
                'id': c.id,
                'job_name': c.job_name,
                'schedule_hour': c.schedule_hour,
                'schedule_minute': c.schedule_minute,
                'days_of_week': c.days_of_week,
                'enabled': c.enabled,
                'last_run_at': c.last_run_at.isoformat() if c.last_run_at else None,
                'last_run_status': c.last_run_status,
                'last_run_message': c.last_run_message
            } for c in configs]
        })


@scheduler_api.route('/config/<job_name>', methods=['GET'])
def get_job_config(job_name):
    """Get configuration for a specific job."""
    with get_session() as session:
        config = session.query(SchedulerConfig).filter_by(job_name=job_name).first()
        if not config:
            return jsonify({'error': f'Job {job_name} not found'}), 404

        return jsonify({
            'id': config.id,
            'job_name': config.job_name,
            'schedule_hour': config.schedule_hour,
            'schedule_minute': config.schedule_minute,
            'days_of_week': config.days_of_week,
            'enabled': config.enabled,
            'last_run_at': config.last_run_at.isoformat() if config.last_run_at else None,
            'last_run_status': config.last_run_status,
            'last_run_message': config.last_run_message
        })


@scheduler_api.route('/config/<job_name>', methods=['PUT'])
def update_job_config(job_name):
    """Update configuration for a specific job.

    Request body (all fields optional):
    {
        "schedule_hour": 5,
        "schedule_minute": 0,
        "days_of_week": "mon,tue,wed,thu,fri",
        "enabled": true
    }
    """
    with get_session() as session:
        config = session.query(SchedulerConfig).filter_by(job_name=job_name).first()
        if not config:
            return jsonify({'error': f'Job {job_name} not found'}), 404

        data = request.get_json()

        # Update fields if provided
        if 'schedule_hour' in data:
            hour = data['schedule_hour']
            if not isinstance(hour, int) or hour < 0 or hour > 23:
                return jsonify({'error': 'schedule_hour must be 0-23'}), 400
            config.schedule_hour = hour

        if 'schedule_minute' in data:
            minute = data['schedule_minute']
            if not isinstance(minute, int) or minute < 0 or minute > 59:
                return jsonify({'error': 'schedule_minute must be 0-59'}), 400
            config.schedule_minute = minute

        if 'days_of_week' in data:
            days = data['days_of_week']
            valid_days = {'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'}
            provided_days = {d.strip().lower() for d in days.split(',')}
            if not provided_days.issubset(valid_days):
                return jsonify({'error': f'Invalid days. Use: {valid_days}'}), 400
            config.days_of_week = days.lower()

        if 'enabled' in data:
            config.enabled = bool(data['enabled'])

        config.updated_at = datetime.now()
        session.commit()

        return jsonify({
            'message': f'Job {job_name} updated successfully',
            'config': {
                'job_name': config.job_name,
                'schedule_hour': config.schedule_hour,
                'schedule_minute': config.schedule_minute,
                'days_of_week': config.days_of_week,
                'enabled': config.enabled
            }
        })


@scheduler_api.route('/config/<job_name>/toggle', methods=['POST'])
def toggle_job(job_name):
    """Enable or disable a job."""
    with get_session() as session:
        config = session.query(SchedulerConfig).filter_by(job_name=job_name).first()
        if not config:
            return jsonify({'error': f'Job {job_name} not found'}), 404

        config.enabled = not config.enabled
        config.updated_at = datetime.now()
        session.commit()

        return jsonify({
            'message': f'Job {job_name} {"enabled" if config.enabled else "disabled"}',
            'enabled': config.enabled
        })


@scheduler_api.route('/history', methods=['GET'])
def get_scrape_history():
    """Get recent scrape history.

    Query params:
        limit: Number of records to return (default 20)
        scrape_type: Filter by type ('initial', 'daily')
    """
    limit = request.args.get('limit', 20, type=int)
    scrape_type = request.args.get('scrape_type')

    with get_session() as session:
        query = session.query(ScrapeLog).order_by(ScrapeLog.started_at.desc())

        if scrape_type:
            query = query.filter_by(scrape_type=scrape_type)

        logs = query.limit(limit).all()

        history = []
        for log in logs:
            # Get tasks for this log
            tasks = session.query(ScrapeLogTask).filter_by(
                scrape_log_id=log.id
            ).order_by(ScrapeLogTask.task_order).all()

            history.append({
                'id': log.id,
                'scrape_type': log.scrape_type,
                'county_code': log.county_code,
                'start_date': log.start_date.isoformat() if log.start_date else None,
                'end_date': log.end_date.isoformat() if log.end_date else None,
                'cases_found': log.cases_found,
                'cases_processed': log.cases_processed,
                'status': log.status,
                'error_message': log.error_message,
                'started_at': log.started_at.isoformat() if log.started_at else None,
                'completed_at': log.completed_at.isoformat() if log.completed_at else None,
                'acknowledged_at': log.acknowledged_at.isoformat() if log.acknowledged_at else None,
                'tasks': [{
                    'id': task.id,
                    'task_name': task.task_name,
                    'task_order': task.task_order,
                    'items_checked': task.items_checked,
                    'items_found': task.items_found,
                    'items_processed': task.items_processed,
                    'started_at': task.started_at.isoformat() if task.started_at else None,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                    'status': task.status,
                    'error_message': task.error_message
                } for task in tasks]
            })

        return jsonify({'history': history})


@scheduler_api.route('/acknowledge/<int:log_id>', methods=['POST'])
def acknowledge_scrape_log(log_id):
    """Acknowledge a failed scrape to dismiss the warning.

    This marks the scrape as reviewed/acknowledged so it won't show
    in the active warnings banner.
    """
    with get_session() as session:
        log = session.query(ScrapeLog).filter_by(id=log_id).first()
        if not log:
            return jsonify({'error': f'Scrape log {log_id} not found'}), 404

        log.acknowledged_at = datetime.now()
        session.commit()

        return jsonify({
            'message': f'Scrape log {log_id} acknowledged',
            'acknowledged_at': log.acknowledged_at.isoformat()
        })


@scheduler_api.route('/run/<job_name>', methods=['POST'])
def trigger_job(job_name):
    """Manually trigger a job to run immediately.

    Request body (optional):
    {
        "target_date": "2025-12-02"  // Defaults to yesterday
    }

    Note: This runs synchronously and may take several minutes.
    For production, consider using a task queue (Celery, etc.)
    """
    if job_name != 'daily_scrape':
        return jsonify({'error': f'Unknown job: {job_name}'}), 404

    data = request.get_json() or {}

    from datetime import timedelta
    from scraper.date_range_scrape import run_date_range_scrape

    # Determine target date
    if 'target_date' in data:
        try:
            target_date = datetime.strptime(data['target_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    else:
        target_date = (datetime.now() - timedelta(days=1)).date()

    try:
        result = run_date_range_scrape(
            start_date=target_date,
            end_date=target_date
        )

        # Update job status
        with get_session() as session:
            config = session.query(SchedulerConfig).filter_by(job_name=job_name).first()
            if config:
                config.last_run_at = datetime.now()
                config.last_run_status = result['status']
                config.last_run_message = f"Manual run: {result['cases_processed']} cases from {target_date}"
                session.commit()

        return jsonify({
            'status': result['status'],
            'target_date': str(target_date),
            'cases_processed': result['cases_processed'],
            'error': result.get('error')
        })

    except Exception as e:
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500
