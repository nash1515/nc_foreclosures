"""Scheduler service for automated daily scrapes.

This service reads configuration from the database and runs scheduled jobs.
The schedule can be modified via the frontend API.

Usage:
    python scheduler/scheduler_service.py

The service will:
1. Check scheduler_config table for job settings
2. Run daily_scrape at the configured time (default: 5 AM Mon-Fri)
3. Scrape cases from the previous day
4. Update last_run_at/last_run_status in the database
"""

import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.connection import get_session
from database.models import SchedulerConfig
from scraper.daily_scrape import run_daily_tasks
from common.logger import setup_logger

logger = setup_logger(__name__)

# Day name mapping
DAY_MAP = {
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
}


class SchedulerService:
    """Service that manages scheduled scraping jobs."""

    def __init__(self):
        self.running = True
        self.check_interval = 60  # Check every 60 seconds

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def get_job_config(self, job_name):
        """Get job configuration from database."""
        with get_session() as session:
            config = session.query(SchedulerConfig).filter_by(job_name=job_name).first()
            if config:
                return {
                    'id': config.id,
                    'job_name': config.job_name,
                    'schedule_hour': config.schedule_hour,
                    'schedule_minute': config.schedule_minute,
                    'days_of_week': config.days_of_week,
                    'enabled': config.enabled,
                    'last_run_at': config.last_run_at
                }
            return None

    def update_job_status(self, job_name, status, message=None):
        """Update job status in database after run."""
        with get_session() as session:
            config = session.query(SchedulerConfig).filter_by(job_name=job_name).first()
            if config:
                config.last_run_at = datetime.now()
                config.last_run_status = status
                config.last_run_message = message
                session.commit()
                logger.info(f"Updated job '{job_name}' status: {status}")

    def should_run_job(self, config):
        """Check if a job should run now based on its schedule."""
        if not config or not config['enabled']:
            return False

        now = datetime.now()

        # Check if today is a scheduled day
        days = [d.strip().lower() for d in config['days_of_week'].split(',')]
        current_day = now.strftime('%a').lower()

        if current_day not in days:
            return False

        # Check if we're at the scheduled time (within the check interval)
        scheduled_hour = config['schedule_hour']
        scheduled_minute = config['schedule_minute']

        if now.hour != scheduled_hour:
            return False

        if now.minute != scheduled_minute:
            return False

        # Check if we already ran today
        last_run = config['last_run_at']
        if last_run:
            if last_run.date() == now.date():
                return False

        return True

    def run_daily_scrape(self):
        """Execute the full daily scrape job (all 4 tasks)."""
        logger.info("=" * 60)
        logger.info("STARTING SCHEDULED DAILY SCRAPE (ALL TASKS)")
        logger.info("=" * 60)

        # Calculate yesterday's date
        yesterday = (datetime.now() - timedelta(days=1)).date()
        logger.info(f"Target date for new cases: {yesterday}")
        logger.info("Tasks: search_new + monitor_existing + validate + reclassify")

        try:
            # Run all 4 daily tasks with 8 parallel browsers for monitoring
            result = run_daily_tasks(
                target_date=yesterday,
                search_new=True,
                monitor_existing=True,
                dry_run=False
            )

            # Build summary message from results
            new_cases = 0
            if result.get('new_case_search'):
                new_cases = result['new_case_search'].get('cases_processed', 0)

            monitored = 0
            events_added = 0
            classifications_changed = 0
            if result.get('case_monitoring'):
                monitored = result['case_monitoring'].get('cases_checked', 0)
                events_added = result['case_monitoring'].get('events_added', 0)
                classifications_changed = result['case_monitoring'].get('classifications_changed', 0)

            # Check for errors
            errors = result.get('errors', [])
            if errors:
                message = f"Completed with {len(errors)} errors. New: {new_cases}, Monitored: {monitored}, Events: {events_added}"
                logger.warning(f"PARTIAL SUCCESS: {message}")
                self.update_job_status('daily_scrape', 'partial', message)
            else:
                message = f"New cases: {new_cases}, Monitored: {monitored}, Events added: {events_added}, Classifications changed: {classifications_changed}"
                logger.info(f"SUCCESS: {message}")
                self.update_job_status('daily_scrape', 'success', message)

        except Exception as e:
            message = f"Exception during daily scrape: {str(e)}"
            logger.exception(message)
            self.update_job_status('daily_scrape', 'failed', message)

    def run(self):
        """Main scheduler loop."""
        logger.info("=" * 60)
        logger.info("SCHEDULER SERVICE STARTED")
        logger.info("=" * 60)

        # Log initial configuration
        config = self.get_job_config('daily_scrape')
        if config:
            logger.info(f"Daily scrape schedule: {config['schedule_hour']:02d}:{config['schedule_minute']:02d}")
            logger.info(f"Days: {config['days_of_week']}")
            logger.info(f"Enabled: {config['enabled']}")
        else:
            logger.warning("No 'daily_scrape' job configured in database")

        logger.info(f"Checking every {self.check_interval} seconds...")
        logger.info("=" * 60)

        while self.running:
            try:
                # Reload config each iteration (allows live updates from frontend)
                config = self.get_job_config('daily_scrape')

                if self.should_run_job(config):
                    self.run_daily_scrape()

                # Sleep for the check interval
                time.sleep(self.check_interval)

            except Exception as e:
                logger.exception(f"Error in scheduler loop: {e}")
                time.sleep(self.check_interval)

        logger.info("Scheduler service stopped")


def main():
    """Entry point for the scheduler service."""
    service = SchedulerService()
    service.run()


if __name__ == '__main__':
    main()
