#!/usr/bin/env python3
"""Re-scrape the 4 problem cases to download documents and extract bid data."""

from scraper.case_monitor import CaseMonitor
from database.connection import get_session
from database.models import Case

# Get the 4 problem cases
problem_ids = [1545, 1035, 1288, 1311]

with get_session() as session:
    cases = session.query(Case).filter(Case.id.in_(problem_ids)).all()
    session.expunge_all()

print(f'Found {len(cases)} cases to process:')
for c in cases:
    print(f'  {c.case_number} (id={c.id}): bid={c.current_bid_amount}, deadline={c.next_bid_deadline}')

# Run the monitor on just these cases
monitor = CaseMonitor(max_workers=1, headless=False)
results = monitor.run(cases=cases)
print(f'Results: {results}')
