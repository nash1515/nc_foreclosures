#!/bin/bash
# Daily scrape wrapper script for NC Foreclosures
#
# This script is designed to be run via cron or manually.
# It sets up the environment and runs the daily scrape.
#
# Usage:
#   ./scripts/run_daily.sh              # Run all daily tasks
#   ./scripts/run_daily.sh --search-only    # Search new cases only
#   ./scripts/run_daily.sh --monitor-only   # Monitor existing only
#   ./scripts/run_daily.sh --dry-run        # Show what would be done
#
# Cron example (run at 6 AM daily):
#   0 6 * * * /home/ahn/projects/nc_foreclosures/scripts/run_daily.sh >> /home/ahn/projects/nc_foreclosures/logs/cron.log 2>&1

set -e

# Configuration
PROJECT_DIR="/home/ahn/projects/nc_foreclosures"
LOG_DIR="${PROJECT_DIR}/logs"
VENV_DIR="${PROJECT_DIR}/venv"
LOG_FILE="${LOG_DIR}/daily_$(date +%Y%m%d_%H%M%S).log"

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Change to project directory
cd "${PROJECT_DIR}"

# Activate virtual environment
source "${VENV_DIR}/bin/activate"

# Set PYTHONPATH
export PYTHONPATH="${PROJECT_DIR}"

# Log start
echo "========================================" | tee -a "${LOG_FILE}"
echo "Daily scrape started: $(date)" | tee -a "${LOG_FILE}"
echo "========================================" | tee -a "${LOG_FILE}"

# Ensure PostgreSQL is running (WSL2 specific)
if ! pgrep -x "postgres" > /dev/null; then
    echo "PostgreSQL not running, attempting to start..." | tee -a "${LOG_FILE}"
    echo "ahn" | sudo -S service postgresql start 2>/dev/null || true
    sleep 2
fi

# Run the daily scrape
python scraper/daily_scrape.py "$@" 2>&1 | tee -a "${LOG_FILE}"
EXIT_CODE=${PIPESTATUS[0]}

# Log end
echo "========================================" | tee -a "${LOG_FILE}"
echo "Daily scrape finished: $(date)" | tee -a "${LOG_FILE}"
echo "Exit code: ${EXIT_CODE}" | tee -a "${LOG_FILE}"
echo "Log file: ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "========================================" | tee -a "${LOG_FILE}"

# Clean up old logs (keep last 30 days)
find "${LOG_DIR}" -name "daily_*.log" -mtime +30 -delete 2>/dev/null || true

exit ${EXIT_CODE}
