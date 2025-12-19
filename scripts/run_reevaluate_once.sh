#!/bin/bash
cd /home/ahn/projects/nc_foreclosures
source venv/bin/activate
PYTHONPATH=/home/ahn/projects/nc_foreclosures python3 scripts/reevaluate_dismissed_cases.py --workers 4 >> logs/reevaluate_dismissed.log 2>&1
# Remove self from crontab after running
crontab -l | grep -v "run_reevaluate_once.sh" | crontab -
