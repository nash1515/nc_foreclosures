# Incremental Scraping Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Change the scraping system to only process NEW events/documents instead of re-processing everything, preventing manual corrections (like address fixes) from being overwritten by bad OCR data.

**Architecture:** Add `event_index` field to track portal event numbers. On each scrape, detect events with index > max stored index, process only those events' documents. Make address "sticky" (first-set wins, never overwrite). Provide explicit "reprocess" command for nuclear reset when needed.

**Tech Stack:** PostgreSQL, SQLAlchemy, Python 3, BeautifulSoup (parsing)

---

## Task 1: Add event_index Column to Database

**Files:**
- Modify: `database/schema.sql` (lines 31-43)
- Modify: `database/models.py` (lines 102-122)

**Step 1: Add column to schema.sql**

In `database/schema.sql`, update the `case_events` table definition:

```sql
-- Case events table - Timeline of events within each case
CREATE TABLE IF NOT EXISTS case_events (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    event_date DATE,
    event_index INTEGER,  -- Portal's Index # for chronological ordering
    event_type VARCHAR(200),
    event_description TEXT,
    filed_by TEXT,  -- Party who filed the event
    filed_against TEXT,  -- Party the event is against
    hearing_date TIMESTAMP,  -- If event has associated hearing
    document_url TEXT,  -- URL to associated document (for Phase 2)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Also add index after line 143:

```sql
CREATE INDEX IF NOT EXISTS idx_case_events_event_index ON case_events(case_id, event_index);
```

**Step 2: Add column to models.py**

In `database/models.py`, update the `CaseEvent` class:

```python
class CaseEvent(Base):
    """Timeline of events within each case."""

    __tablename__ = 'case_events'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    event_date = Column(Date)
    event_index = Column(Integer)  # Portal's Index # for chronological ordering
    event_type = Column(String(200))
    event_description = Column(Text)
    filed_by = Column(Text)  # Party who filed the event
    filed_against = Column(Text)  # Party the event is against
    hearing_date = Column(TIMESTAMP)  # If event has associated hearing
    document_url = Column(Text)  # URL to associated document (for Phase 2)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    case = relationship("Case", back_populates="events")

    def __repr__(self):
        return f"<CaseEvent(case_id={self.case_id}, index={self.event_index}, type='{self.event_type}')>"
```

**Step 3: Run database migration**

```bash
cd /home/ahn/projects/nc_foreclosures
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "ALTER TABLE case_events ADD COLUMN IF NOT EXISTS event_index INTEGER;"
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "CREATE INDEX IF NOT EXISTS idx_case_events_event_index ON case_events(case_id, event_index);"
```

**Step 4: Verify migration**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d case_events"
```

Expected: Should show `event_index` column of type `integer`

**Step 5: Commit**

```bash
git add database/schema.sql database/models.py
git commit -m "feat: add event_index column to case_events table

Tracks the portal's Index # for each event to enable incremental
processing. Events with index > max stored will be treated as new."
```

---

## Task 2: Update Parser to Capture event_index

**Files:**
- Modify: `scraper/page_parser.py` (lines 489-538)

**Step 1: Update event_data dictionary to include event_index**

In `scraper/page_parser.py`, find the `parse_case_detail` function. Around line 489, the code already extracts the index:

```python
# Extract Index number
index_match = re.search(r'Index\s*#\s*(\d+)', event_text)
```

But it's never used. Update the event_data dictionary (around line 526-538) to include it:

```python
        if event_date or event_type:
            event_data = {
                'event_date': event_date,
                'event_type': event_type,
                'event_index': int(index_match.group(1)) if index_match else None,  # ADD THIS
                'event_description': event_description,
                'document_title': document_title,  # Document title for classification
                'filed_by': filed_by_match.group(1).strip() if filed_by_match else None,
                'filed_against': against_match.group(1).strip() if against_match else None,
                'hearing_date': f"{hearing_match.group(1)} {hearing_match.group(2)}" if hearing_match else None,
                'document_url': None,  # Will need JS execution to get actual URL
                'has_document': has_document
            }
            case_data['events'].append(event_data)
            logger.debug(f"Event: {event_date} - {event_type} (Index #{event_data['event_index']}) - Doc: {document_title}")
```

**Step 2: Test parser manually**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "
from scraper.page_parser import parse_case_detail

# Simple test with mock HTML containing Index #
html = '''
<div ng-repeat=\"event in events\">
  01/22/2026
  Upset Bid Filed
  Bid Amount \$23,365.65
  Index # 36
</div>
'''
result = parse_case_detail(html)
events = result.get('events', [])
if events:
    print(f'Event index: {events[0].get(\"event_index\")}')
    assert events[0].get('event_index') == 36, 'Index not captured!'
    print('SUCCESS: event_index captured correctly')
else:
    print('No events parsed (expected for minimal HTML)')
"
```

**Step 3: Commit**

```bash
git add scraper/page_parser.py
git commit -m "feat: capture event_index from portal in parser

The parser now extracts Index # from each event div and includes
it in the event_data dictionary for storage."
```

---

## Task 3: Update Event Storage to Save event_index

**Files:**
- Modify: `scraper/case_monitor.py` (lines 646-675)

**Step 1: Update add_new_events to store event_index**

In `scraper/case_monitor.py`, find the `add_new_events` method and update it:

```python
    def add_new_events(self, case_id: int, new_events: List[Dict]):
        """
        Add new events to the database.

        Args:
            case_id: Database ID of the case
            new_events: List of event dicts to add
        """
        with get_session() as session:
            for event_data in new_events:
                # Parse event date
                event_date = None
                if event_data.get('event_date'):
                    try:
                        event_date = datetime.strptime(event_data['event_date'], '%m/%d/%Y').date()
                    except Exception as e:
                        logger.warning(f"Event date parse failed for {event_data}: {e}")

                event = CaseEvent(
                    case_id=case_id,
                    event_date=event_date,
                    event_index=event_data.get('event_index'),  # ADD THIS
                    event_type=event_data.get('event_type'),
                    event_description=event_data.get('event_description'),
                    filed_by=event_data.get('filed_by'),
                    filed_against=event_data.get('filed_against'),
                    document_url=event_data.get('document_url')
                )
                session.add(event)
                logger.info(f"  Added event: {event.event_type} (Index #{event.event_index})")

            session.commit()
```

**Step 2: Commit**

```bash
git add scraper/case_monitor.py
git commit -m "feat: store event_index when adding new events

New events now have their portal Index # saved to the database
for incremental processing detection."
```

---

## Task 4: Update Event Detection to Use Index-Based Comparison

**Files:**
- Modify: `scraper/case_monitor.py` (lines 191-219)

**Step 1: Add helper method to get max event index**

Add this new method to the `CaseMonitor` class (before `detect_new_events`):

```python
    def get_max_event_index(self, case_id: int) -> int:
        """
        Get the highest event_index stored for a case.

        Args:
            case_id: Database ID of the case

        Returns:
            Highest event_index, or 0 if none exist
        """
        with get_session() as session:
            result = session.query(func.max(CaseEvent.event_index))\
                .filter(CaseEvent.case_id == case_id).scalar()
            return result or 0
```

**Step 2: Update detect_new_events to use index-based detection**

Replace the existing `detect_new_events` method:

```python
    def detect_new_events(
        self,
        existing_events: List[Dict],
        parsed_events: List[Dict],
        case_id: int = None
    ) -> List[Dict]:
        """
        Compare parsed events against existing to find new ones.

        Uses event_index for comparison when available (preferred).
        Falls back to signature-based comparison for events without index.

        Args:
            existing_events: Events already in database
            parsed_events: Events parsed from current page
            case_id: Optional case ID for index-based detection

        Returns:
            List of new events not in database
        """
        new_events = []

        # Try index-based detection first (preferred)
        if case_id:
            max_index = self.get_max_event_index(case_id)
            if max_index > 0:
                # Use index-based detection
                for event in parsed_events:
                    event_index = event.get('event_index')
                    if event_index and event_index > max_index:
                        new_events.append(event)
                        logger.debug(f"  New event by index: #{event_index} > #{max_index}")

                # If we found new events by index, return them
                if new_events:
                    return new_events

                # If no new events by index and max_index exists, nothing is new
                # (all parsed events have index <= max_index)
                if all(e.get('event_index') for e in parsed_events):
                    return []

        # Fallback: signature-based detection (for cases without index data yet)
        existing_signatures = set()
        for e in existing_events:
            sig = (e.get('event_date'), (e.get('event_type') or '').strip().lower())
            existing_signatures.add(sig)

        for event in parsed_events:
            sig = (event.get('event_date'), (event.get('event_type') or '').strip().lower())
            if sig not in existing_signatures and event.get('event_type'):
                new_events.append(event)

        return new_events
```

**Step 3: Update process_case to pass case_id**

In `process_case` method (around line 718-719), update the call:

```python
            # Find new events
            new_events = self.detect_new_events(existing_events, parsed_events, case_id=case.id)
```

**Step 4: Add import for func**

At the top of `case_monitor.py`, ensure `func` is imported:

```python
from sqlalchemy import func
```

**Step 5: Commit**

```bash
git add scraper/case_monitor.py
git commit -m "feat: use event_index for new event detection

Detect new events by comparing event_index to max stored index.
Falls back to signature-based detection for legacy cases without
index data."
```

---

## Task 5: Make Address Extraction Sticky (Never Overwrite)

**Files:**
- Modify: `extraction/extractor.py` (lines 1570-1594)

**Step 1: Remove quality-based overwrite logic**

In `extraction/extractor.py`, find the `update_case_with_extracted_data` function. Replace the address update logic (around lines 1570-1594):

**BEFORE:**
```python
if extracted['property_address']:
    new_quality = extracted.get('address_quality', 99)
    should_update = False

    if not case.property_address:
        should_update = True
    elif new_quality is not None and new_quality <= ADDRESS_QUALITY_THRESHOLD:
        if case.property_address != extracted['property_address']:
            should_update = True
            logger.info(f"Overwriting address (quality={new_quality} <= {ADDRESS_QUALITY_THRESHOLD})")

    if should_update:
        case.property_address = extracted['property_address']
```

**AFTER:**
```python
# Address is STICKY - only set if not already present
# Manual corrections are preserved; use reprocess_case() for full reset
if extracted['property_address'] and not case.property_address:
    case.property_address = extracted['property_address']
    logger.info(f"Set property address: {extracted['property_address'][:50]}...")
elif extracted['property_address'] and case.property_address:
    logger.debug(f"Preserving existing address (sticky): {case.property_address[:50]}...")
```

**Step 2: Commit**

```bash
git add extraction/extractor.py
git commit -m "fix: make property_address sticky (first-set wins)

Address is now only set if empty, never overwritten. This prevents
bad OCR from overwriting manual corrections. Use reprocess_case()
for full reset when needed."
```

---

## Task 6: Add Incremental Extraction Support

**Files:**
- Modify: `extraction/extractor.py` (add new function parameter)

**Step 1: Add event_ids parameter to update_case_with_extracted_data**

Find the function signature and update it:

```python
def update_case_with_extracted_data(case_id: int, event_ids: List[int] = None) -> bool:
    """
    Update case with data extracted from documents.

    Args:
        case_id: ID of the case to update
        event_ids: If provided, only process documents linked to these events.
                   If None, process ALL documents (reprocess mode).

    Returns:
        True if any data was updated, False otherwise
    """
```

**Step 2: Update document query to filter by event_ids**

Inside the function, find where documents are queried (in `extract_all_from_case` or similar). Update to filter:

```python
def extract_all_from_case(case_id: int, event_ids: List[int] = None) -> Dict[str, Any]:
    """
    Extract all data from documents for a case.

    Args:
        case_id: Case to extract from
        event_ids: If provided, only process documents linked to these events.
    """
    # ... existing setup code ...

    with get_session() as session:
        query = session.query(Document).filter(Document.case_id == case_id)

        if event_ids is not None:
            # Incremental mode: only documents linked to specified events
            query = query.filter(Document.event_id.in_(event_ids))
            logger.info(f"Incremental extraction: processing {len(event_ids)} events' documents")
        else:
            # Reprocess mode: all documents
            logger.info(f"Full extraction: processing all documents for case {case_id}")

        documents = query.order_by(Document.created_at.desc()).all()
```

Also update `update_case_with_extracted_data` to pass `event_ids`:

```python
def update_case_with_extracted_data(case_id: int, event_ids: List[int] = None) -> bool:
    # ...
    extracted = extract_all_from_case(case_id, event_ids=event_ids)
    # ... rest of function
```

**Step 3: Add List import if needed**

```python
from typing import List, Dict, Any, Optional
```

**Step 4: Commit**

```bash
git add extraction/extractor.py
git commit -m "feat: add incremental extraction support

update_case_with_extracted_data now accepts optional event_ids
parameter. When provided, only documents linked to those events
are processed. When None, all documents are processed (reprocess)."
```

---

## Task 7: Update process_case to Use Incremental Extraction

**Files:**
- Modify: `scraper/case_monitor.py` (around line 860)

**Step 1: Get new event IDs and pass to extraction**

In `process_case`, after adding new events, get their IDs and pass to extraction:

```python
            if new_events:
                logger.info(f"  Found {len(new_events)} new events")
                for event in new_events:
                    logger.info(f"    - {event.get('event_date')}: {event.get('event_type')} (Index #{event.get('event_index')})")

                # Add new events to database
                self.add_new_events(case.id, new_events)
                result['events_added'] = len(new_events)

                # Get the IDs of newly added events for incremental extraction
                new_event_ids = self._get_recent_event_ids(case.id, len(new_events))

                # ... existing event type handling code ...
```

**Step 2: Add helper method to get recent event IDs**

Add this method to CaseMonitor class:

```python
    def _get_recent_event_ids(self, case_id: int, count: int) -> List[int]:
        """
        Get IDs of the most recently added events for a case.

        Args:
            case_id: Case ID
            count: Number of recent events to get

        Returns:
            List of event IDs
        """
        with get_session() as session:
            events = session.query(CaseEvent.id)\
                .filter(CaseEvent.case_id == case_id)\
                .order_by(CaseEvent.created_at.desc())\
                .limit(count)\
                .all()
            return [e.id for e in events]
```

**Step 3: Update extraction call to pass event IDs**

Around line 860, update the extraction call:

```python
            # Run extraction - incremental if new events, skip if no changes
            if new_events:
                # Incremental: only process new events' documents
                extraction_updated = update_case_with_extracted_data(case.id, event_ids=new_event_ids)
            else:
                # No new events - skip extraction entirely (preserves existing data)
                extraction_updated = False
                logger.debug(f"  No new events - skipping extraction")

            if extraction_updated:
                logger.info(f"  Extraction updated case data")
                result['extraction_updated'] = True
```

**Step 4: Commit**

```bash
git add scraper/case_monitor.py
git commit -m "feat: use incremental extraction in process_case

Only run extraction when new events are found, and only process
documents linked to those new events. Skip extraction entirely
when no new events detected (preserves existing data)."
```

---

## Task 8: Create Reprocess Command

**Files:**
- Create: `scripts/reprocess_case.py`

**Step 1: Create the reprocess script**

```python
#!/usr/bin/env python3
"""
Reprocess a case - nuclear reset that re-extracts all data from all documents.

Usage:
    python scripts/reprocess_case.py <case_number>
    python scripts/reprocess_case.py --case-id <id>
    python scripts/reprocess_case.py --all-upset-bid  # Reprocess all upset_bid cases
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import Case, CaseEvent, Document
from extraction.extractor import update_case_with_extracted_data
from common.logger import setup_logger

logger = setup_logger(__name__)


def reprocess_case(case_id: int, clear_address: bool = True) -> bool:
    """
    Reprocess a case - clear extracted fields and re-extract from all documents.

    Args:
        case_id: ID of case to reprocess
        clear_address: If True, clear property_address (default True for full reset)

    Returns:
        True if successful
    """
    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            logger.error(f"Case ID {case_id} not found")
            return False

        logger.info(f"Reprocessing case {case.case_number} (ID: {case_id})")

        # Clear extracted fields for full re-extraction
        if clear_address:
            old_address = case.property_address
            case.property_address = None
            logger.info(f"  Cleared address: {old_address}")

        # Note: We don't clear bid amounts - those should come from events
        # Note: We don't clear sale_date - that's event-derived

        # Clear extraction_attempted_at on all documents to force re-OCR if needed
        docs_cleared = session.query(Document)\
            .filter(Document.case_id == case_id)\
            .update({Document.extraction_attempted_at: None})
        logger.info(f"  Reset extraction flag on {docs_cleared} documents")

        session.commit()

    # Run full extraction (event_ids=None means all documents)
    logger.info(f"  Running full extraction...")
    result = update_case_with_extracted_data(case_id, event_ids=None)

    if result:
        logger.info(f"  Reprocess complete - data updated")
    else:
        logger.info(f"  Reprocess complete - no changes")

    return True


def main():
    parser = argparse.ArgumentParser(description='Reprocess a case (full re-extraction)')
    parser.add_argument('case_number', nargs='?', help='Case number (e.g., 24-CVS-1234)')
    parser.add_argument('--case-id', type=int, help='Case ID (database primary key)')
    parser.add_argument('--all-upset-bid', action='store_true',
                        help='Reprocess all upset_bid cases')
    parser.add_argument('--keep-address', action='store_true',
                        help='Keep existing address (only re-extract other fields)')

    args = parser.parse_args()

    if args.all_upset_bid:
        with get_session() as session:
            cases = session.query(Case).filter_by(classification='upset_bid').all()
            logger.info(f"Reprocessing {len(cases)} upset_bid cases...")
            for case in cases:
                reprocess_case(case.id, clear_address=not args.keep_address)
    elif args.case_id:
        reprocess_case(args.case_id, clear_address=not args.keep_address)
    elif args.case_number:
        with get_session() as session:
            case = session.query(Case).filter_by(case_number=args.case_number).first()
            if not case:
                logger.error(f"Case {args.case_number} not found")
                sys.exit(1)
            reprocess_case(case.id, clear_address=not args.keep_address)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
```

**Step 2: Make executable**

```bash
chmod +x /home/ahn/projects/nc_foreclosures/scripts/reprocess_case.py
```

**Step 3: Test the script help**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python scripts/reprocess_case.py --help
```

Expected: Shows usage information

**Step 4: Commit**

```bash
git add scripts/reprocess_case.py
git commit -m "feat: add reprocess_case script for full re-extraction

Nuclear reset that clears extracted fields and re-processes all
documents. Use when OCR/extraction improvements warrant full reset
or when data corruption needs fixing."
```

---

## Task 9: Run Document-Event Backfill

**Files:**
- Use existing: `scripts/backfill_document_events.py`

**Step 1: Check current unlinked document count**

```bash
cd /home/ahn/projects/nc_foreclosures
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT
    COUNT(*) FILTER (WHERE event_id IS NULL) as unlinked,
    COUNT(*) FILTER (WHERE event_id IS NOT NULL) as linked,
    COUNT(*) as total
FROM documents;
"
```

**Step 2: Run the backfill script**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python scripts/backfill_document_events.py
```

**Step 3: Verify improvement**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT
    COUNT(*) FILTER (WHERE event_id IS NULL) as unlinked,
    COUNT(*) FILTER (WHERE event_id IS NOT NULL) as linked,
    COUNT(*) as total
FROM documents;
"
```

Expected: `unlinked` count should be significantly reduced

**Step 4: Commit any changes to backfill script if needed**

```bash
git add scripts/backfill_document_events.py
git commit -m "chore: run document-event backfill" --allow-empty
```

---

## Task 10: Create Event Index Backfill Script

**Files:**
- Create: `scripts/backfill_event_index.py`

This script will re-scrape all cases to populate event_index for existing events.

**Step 1: Create the backfill script**

```python
#!/usr/bin/env python3
"""
Backfill event_index for existing case_events by re-scraping cases.

This script:
1. Gets all cases that have events without event_index
2. Re-scrapes each case to get current event data with Index #
3. Matches existing events by signature and updates their event_index

Usage:
    python scripts/backfill_event_index.py
    python scripts/backfill_event_index.py --dry-run
    python scripts/backfill_event_index.py --limit 10
"""

import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from playwright.sync_api import sync_playwright
from database.connection import get_session
from database.models import Case, CaseEvent
from scraper.page_parser import parse_case_detail
from common.logger import setup_logger

logger = setup_logger(__name__)


def fetch_case_page(page, case_url: str, max_retries: int = 3) -> str:
    """Fetch case detail page with retry logic."""
    for attempt in range(max_retries):
        try:
            page.goto(case_url, wait_until='networkidle', timeout=30000)
            page.wait_for_selector('table.roa-caseinfo-info-rows', timeout=15000)
            return page.content()
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
            else:
                raise


def backfill_case_events(case: Case, page, dry_run: bool = False) -> int:
    """
    Backfill event_index for a case by re-scraping.

    Returns:
        Number of events updated
    """
    logger.info(f"Processing {case.case_number}...")

    try:
        html = fetch_case_page(page, case.case_url)
        case_data = parse_case_detail(html)
        parsed_events = case_data.get('events', [])

        if not parsed_events:
            logger.warning(f"  No events parsed from page")
            return 0

        # Create lookup by signature
        parsed_by_sig = {}
        for event in parsed_events:
            if event.get('event_index'):
                sig = (event.get('event_date'), (event.get('event_type') or '').strip().lower())
                parsed_by_sig[sig] = event['event_index']

        if not parsed_by_sig:
            logger.warning(f"  No events with Index # found on page")
            return 0

        # Update existing events
        updated = 0
        with get_session() as session:
            db_events = session.query(CaseEvent).filter(
                CaseEvent.case_id == case.id,
                CaseEvent.event_index.is_(None)
            ).all()

            for db_event in db_events:
                # Format date to match parser output
                event_date_str = db_event.event_date.strftime('%m/%d/%Y') if db_event.event_date else None
                sig = (event_date_str, (db_event.event_type or '').strip().lower())

                if sig in parsed_by_sig:
                    new_index = parsed_by_sig[sig]
                    if not dry_run:
                        db_event.event_index = new_index
                    logger.debug(f"  {db_event.event_type} ({event_date_str}) -> Index #{new_index}")
                    updated += 1

            if not dry_run:
                session.commit()

        logger.info(f"  Updated {updated} events with Index #")
        return updated

    except Exception as e:
        logger.error(f"  Error processing {case.case_number}: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Backfill event_index for existing events')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated')
    parser.add_argument('--limit', type=int, help='Limit number of cases to process')
    parser.add_argument('--classification', type=str, help='Only process cases with this classification')

    args = parser.parse_args()

    # Find cases with events missing event_index
    with get_session() as session:
        query = session.query(Case).join(CaseEvent).filter(
            CaseEvent.event_index.is_(None)
        ).distinct()

        if args.classification:
            query = query.filter(Case.classification == args.classification)

        cases = query.all()

        if args.limit:
            cases = cases[:args.limit]

        logger.info(f"Found {len(cases)} cases with events missing event_index")

    if not cases:
        logger.info("No cases need backfill")
        return

    total_updated = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False for Angular
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()

        try:
            for i, case in enumerate(cases):
                logger.info(f"[{i+1}/{len(cases)}] Processing {case.case_number}")
                updated = backfill_case_events(case, page, dry_run=args.dry_run)
                total_updated += updated

                # Small delay to be nice to the server
                time.sleep(1)

        finally:
            browser.close()

    action = "Would update" if args.dry_run else "Updated"
    logger.info(f"Backfill complete: {action} {total_updated} events across {len(cases)} cases")


if __name__ == '__main__':
    main()
```

**Step 2: Make executable**

```bash
chmod +x /home/ahn/projects/nc_foreclosures/scripts/backfill_event_index.py
```

**Step 3: Commit**

```bash
git add scripts/backfill_event_index.py
git commit -m "feat: add backfill script for event_index

Re-scrapes cases to populate event_index on existing events.
Required for transition to index-based new event detection."
```

---

## Task 11: Run Event Index Backfill

**Step 1: Check current state**

```bash
cd /home/ahn/projects/nc_foreclosures
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT
    COUNT(*) FILTER (WHERE event_index IS NULL) as missing_index,
    COUNT(*) FILTER (WHERE event_index IS NOT NULL) as has_index,
    COUNT(*) as total
FROM case_events;
"
```

**Step 2: Test with dry run first**

```bash
PYTHONPATH=$(pwd) python scripts/backfill_event_index.py --dry-run --limit 5
```

**Step 3: Run full backfill (upset_bid cases first)**

```bash
PYTHONPATH=$(pwd) python scripts/backfill_event_index.py --classification upset_bid
```

**Step 4: Run for remaining cases**

```bash
PYTHONPATH=$(pwd) python scripts/backfill_event_index.py
```

**Step 5: Verify results**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT
    COUNT(*) FILTER (WHERE event_index IS NULL) as missing_index,
    COUNT(*) FILTER (WHERE event_index IS NOT NULL) as has_index,
    COUNT(*) as total
FROM case_events;
"
```

Expected: `has_index` should be significantly higher

---

## Task 12: Fix the Forest Fern Lane Address

**Step 1: Find the case**

```bash
cd /home/ahn/projects/nc_foreclosures
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT id, case_number, property_address
FROM cases
WHERE property_address LIKE '%Forest Fern%' OR property_address LIKE '%/312%';
"
```

**Step 2: Manually fix the address**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
UPDATE cases
SET property_address = '1312 Forest Fern Lane, Fuquay Varina, NC 27526'
WHERE property_address LIKE '%/312 Forest Fern%';
"
```

**Step 3: Verify fix**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT id, case_number, property_address
FROM cases
WHERE property_address LIKE '%Forest Fern%';
"
```

Expected: Address now shows `1312 Forest Fern Lane...`

---

## Task 13: Test the Complete Flow

**Step 1: Run a test scrape on a single case**

Pick an upset_bid case and run case_monitor on just that case:

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "
from database.connection import get_session
from database.models import Case
from scraper.case_monitor import CaseMonitor

# Get an upset_bid case
with get_session() as session:
    case = session.query(Case).filter_by(classification='upset_bid').first()
    if case:
        print(f'Testing with case: {case.case_number}')
        print(f'Current address: {case.property_address}')

        monitor = CaseMonitor(headless=False)
        results = monitor.run(cases=[case])
        print(f'Results: {results}')
    else:
        print('No upset_bid cases found')
"
```

**Step 2: Verify address was NOT overwritten**

Check the case's address is unchanged after the scrape.

**Step 3: Verify the fix works on next daily scrape**

After the next daily scrape runs, check that:
1. Forest Fern Lane address is still `1312` (not `/312`)
2. New events (if any) are detected by index
3. Extraction only runs on new events' documents

---

## Summary

After completing all tasks:

1. **Schema updated** - `event_index` column added to `case_events`
2. **Parser captures index** - `Index #` from portal now stored
3. **Event detection uses index** - New events found by `index > max_stored`
4. **Address is sticky** - First-set wins, never overwritten
5. **Extraction is incremental** - Only new events' documents processed
6. **Reprocess command available** - Nuclear reset when needed
7. **Backfills complete** - Existing events have index, documents linked to events
8. **Forest Fern fixed** - And won't be overwritten again

The system now preserves manual corrections while still capturing new data from new events.
