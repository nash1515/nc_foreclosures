# Self-Diagnosis System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add automatic self-healing for upset_bid cases with missing data after each daily scrape.

**Architecture:** New `scraper/self_diagnosis.py` module with tiered healing (re-extract → re-download → re-scrape). Integrates as Task 5 in daily_scrape.py.

**Tech Stack:** Python, SQLAlchemy, existing extraction/OCR/monitoring modules

---

## Task 1: Create self_diagnosis.py with completeness check

**Files:**
- Create: `scraper/self_diagnosis.py`
- Test: Manual testing via Python REPL

**Step 1: Create the module with imports and completeness checker**

```python
"""Self-diagnosis and healing for upset_bid cases with missing data."""

from typing import Dict, List, Optional
from database.connection import get_session
from database.models import Case, Document, CaseEvent
from common.logger import setup_logger

logger = setup_logger(__name__)

REQUIRED_FIELDS = [
    'case_number',
    'property_address',
    'current_bid_amount',
    'minimum_next_bid',
    'next_bid_deadline',
    'sale_date'
]


def _check_completeness(case: Case) -> List[str]:
    """
    Check which required fields are missing from a case.

    Args:
        case: Case object to check

    Returns:
        List of missing field names (empty if complete)
    """
    missing = []
    for field in REQUIRED_FIELDS:
        value = getattr(case, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def _get_upset_bid_cases() -> List[Case]:
    """Get all upset_bid cases from database."""
    with get_session() as session:
        cases = session.query(Case).filter(
            Case.classification == 'upset_bid'
        ).all()
        session.expunge_all()
        return cases
```

**Step 2: Test completeness checker**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/self-diagnosis
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.self_diagnosis import _check_completeness, _get_upset_bid_cases
cases = _get_upset_bid_cases()
print(f'Found {len(cases)} upset_bid cases')
for c in cases[:3]:
    missing = _check_completeness(c)
    print(f'{c.case_number}: missing {missing if missing else \"none\"}')
"
```

Expected: Shows 3 upset_bid cases with their missing fields (should be empty for all if data is complete)

**Step 3: Commit**

```bash
git add scraper/self_diagnosis.py
git commit -m "feat: add self_diagnosis module with completeness checker"
```

---

## Task 2: Add Tier 1 - Re-extract from existing documents

**Files:**
- Modify: `scraper/self_diagnosis.py`

**Step 1: Add Tier 1 function**

Add after `_get_upset_bid_cases()`:

```python
from extraction.extractor import update_case_with_extracted_data


def _tier1_reextract(case: Case) -> bool:
    """
    Tier 1: Re-run extraction on existing documents.

    Args:
        case: Case to heal

    Returns:
        True if extraction was attempted
    """
    logger.info(f"Case {case.case_number}: Tier 1 (re-extract) - attempting...")
    try:
        updated = update_case_with_extracted_data(case.id)
        if updated:
            logger.info(f"Case {case.case_number}: Tier 1 - extraction updated case")
        else:
            logger.info(f"Case {case.case_number}: Tier 1 - no new data extracted")
        return True
    except Exception as e:
        logger.error(f"Case {case.case_number}: Tier 1 failed - {e}")
        return False
```

**Step 2: Test Tier 1**

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.self_diagnosis import _tier1_reextract, _get_upset_bid_cases
from database.connection import get_session
from database.models import Case

cases = _get_upset_bid_cases()
if cases:
    print(f'Testing tier1 on {cases[0].case_number}')
    _tier1_reextract(cases[0])
"
```

Expected: Shows Tier 1 attempt log messages

**Step 3: Commit**

```bash
git add scraper/self_diagnosis.py
git commit -m "feat: add Tier 1 re-extraction healing"
```

---

## Task 3: Add Tier 2 - Re-download and extract

**Files:**
- Modify: `scraper/self_diagnosis.py`

**Step 1: Add Tier 2 function**

Add after `_tier1_reextract()`:

```python
from ocr.processor import process_case_documents
from scraper.document_downloader import download_case_documents


def _tier2_redownload(case: Case) -> bool:
    """
    Tier 2: Re-download documents and extract.

    Args:
        case: Case to heal

    Returns:
        True if download was attempted
    """
    logger.info(f"Case {case.case_number}: Tier 2 (re-download) - attempting...")
    try:
        # Get events with document URLs
        with get_session() as session:
            events = session.query(CaseEvent).filter(
                CaseEvent.case_id == case.id,
                CaseEvent.document_url.isnot(None)
            ).all()
            event_count = len(events)
            session.expunge_all()

        if event_count == 0:
            logger.info(f"Case {case.case_number}: Tier 2 - no document URLs found")
            return False

        # Re-download documents
        downloaded = download_case_documents(case.id, force=True)
        logger.info(f"Case {case.case_number}: Tier 2 - downloaded {downloaded} documents")

        # OCR the documents
        processed = process_case_documents(case.id)
        logger.info(f"Case {case.case_number}: Tier 2 - processed {processed} documents")

        # Re-extract
        updated = update_case_with_extracted_data(case.id)
        if updated:
            logger.info(f"Case {case.case_number}: Tier 2 - extraction updated case")

        return True
    except Exception as e:
        logger.error(f"Case {case.case_number}: Tier 2 failed - {e}")
        return False
```

**Step 2: Check if download_case_documents exists**

First verify the function exists. If not, we'll need to extract it from date_range_scrape.py or create a simple version. Run:

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
try:
    from scraper.document_downloader import download_case_documents
    print('Function exists')
except ImportError as e:
    print(f'Need to create: {e}')
"
```

If it doesn't exist, create `scraper/document_downloader.py` with the download logic extracted from date_range_scrape.py. Otherwise proceed.

**Step 3: Test Tier 2**

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.self_diagnosis import _tier2_redownload, _get_upset_bid_cases
cases = _get_upset_bid_cases()
if cases:
    print(f'Testing tier2 on {cases[0].case_number}')
    # Dry run - just check it doesn't crash
    print('Tier 2 function defined successfully')
"
```

**Step 4: Commit**

```bash
git add scraper/self_diagnosis.py scraper/document_downloader.py 2>/dev/null
git commit -m "feat: add Tier 2 re-download healing"
```

---

## Task 4: Add Tier 3 - Full re-scrape

**Files:**
- Modify: `scraper/self_diagnosis.py`

**Step 1: Add Tier 3 function**

Add after `_tier2_redownload()`:

```python
from scraper.case_monitor import CaseMonitor


def _tier3_rescrape(case: Case) -> bool:
    """
    Tier 3: Full re-scrape via CaseMonitor.

    Args:
        case: Case to heal

    Returns:
        True if re-scrape was attempted
    """
    logger.info(f"Case {case.case_number}: Tier 3 (re-scrape) - attempting...")
    try:
        monitor = CaseMonitor(max_workers=1, headless=False, max_retries=2)
        results = monitor.run(cases=[case])

        logger.info(f"Case {case.case_number}: Tier 3 - re-scrape complete")

        # OCR any new documents
        processed = process_case_documents(case.id)
        if processed:
            logger.info(f"Case {case.case_number}: Tier 3 - processed {processed} new documents")

        # Extract data
        updated = update_case_with_extracted_data(case.id)
        if updated:
            logger.info(f"Case {case.case_number}: Tier 3 - extraction updated case")

        return True
    except Exception as e:
        logger.error(f"Case {case.case_number}: Tier 3 failed - {e}")
        return False
```

**Step 2: Test Tier 3 syntax**

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.self_diagnosis import _tier3_rescrape
print('Tier 3 function defined successfully')
"
```

**Step 3: Commit**

```bash
git add scraper/self_diagnosis.py
git commit -m "feat: add Tier 3 full re-scrape healing"
```

---

## Task 5: Add main diagnosis function

**Files:**
- Modify: `scraper/self_diagnosis.py`

**Step 1: Add main function**

Add at end of file:

```python
def diagnose_and_heal_upset_bids(dry_run: bool = False) -> Dict:
    """
    Check all upset_bid cases for completeness and attempt self-healing.

    Args:
        dry_run: If True, only check completeness without healing

    Returns:
        Dict with diagnosis results
    """
    results = {
        'cases_checked': 0,
        'cases_incomplete': 0,
        'cases_healed': 0,
        'cases_unresolved': [],
        'healing_attempts': {
            'tier1_reextract': {'attempted': 0, 'succeeded': 0},
            'tier2_redownload': {'attempted': 0, 'succeeded': 0},
            'tier3_rescrape': {'attempted': 0, 'succeeded': 0}
        }
    }

    cases = _get_upset_bid_cases()
    results['cases_checked'] = len(cases)
    logger.info(f"Self-diagnosis: checking {len(cases)} upset_bid cases")

    for case in cases:
        missing = _check_completeness(case)

        if not missing:
            continue  # Already complete

        results['cases_incomplete'] += 1
        logger.info(f"Case {case.case_number}: missing {missing}")

        if dry_run:
            results['cases_unresolved'].append({
                'case_id': case.id,
                'case_number': case.case_number,
                'missing_fields': missing
            })
            continue

        # Tier 1: Re-extract
        results['healing_attempts']['tier1_reextract']['attempted'] += 1
        _tier1_reextract(case)

        # Refresh case and check
        with get_session() as session:
            refreshed = session.query(Case).filter_by(id=case.id).first()
            missing = _check_completeness(refreshed)
            session.expunge(refreshed)

        if not missing:
            results['healing_attempts']['tier1_reextract']['succeeded'] += 1
            results['cases_healed'] += 1
            logger.info(f"Case {case.case_number}: Tier 1 - complete, all fields populated")
            continue

        # Tier 2: Re-download
        results['healing_attempts']['tier2_redownload']['attempted'] += 1
        _tier2_redownload(case)

        with get_session() as session:
            refreshed = session.query(Case).filter_by(id=case.id).first()
            missing = _check_completeness(refreshed)
            session.expunge(refreshed)

        if not missing:
            results['healing_attempts']['tier2_redownload']['succeeded'] += 1
            results['cases_healed'] += 1
            logger.info(f"Case {case.case_number}: Tier 2 - complete, all fields populated")
            continue

        # Tier 3: Full re-scrape
        results['healing_attempts']['tier3_rescrape']['attempted'] += 1
        _tier3_rescrape(case)

        with get_session() as session:
            refreshed = session.query(Case).filter_by(id=case.id).first()
            missing = _check_completeness(refreshed)
            session.expunge(refreshed)

        if not missing:
            results['healing_attempts']['tier3_rescrape']['succeeded'] += 1
            results['cases_healed'] += 1
            logger.info(f"Case {case.case_number}: Tier 3 - complete, all fields populated")
            continue

        # Still incomplete after all tiers
        results['cases_unresolved'].append({
            'case_id': case.id,
            'case_number': case.case_number,
            'missing_fields': missing
        })
        logger.warning(f"Case {case.case_number}: unresolved after all tiers, missing {missing}")

    healed = results['cases_healed']
    unresolved = len(results['cases_unresolved'])
    logger.info(f"Self-diagnosis complete: {results['cases_incomplete']} incomplete, {healed} healed, {unresolved} unresolved")

    return results
```

**Step 2: Test main function (dry run)**

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.self_diagnosis import diagnose_and_heal_upset_bids
results = diagnose_and_heal_upset_bids(dry_run=True)
print(f'Checked: {results[\"cases_checked\"]}')
print(f'Incomplete: {results[\"cases_incomplete\"]}')
print(f'Unresolved: {len(results[\"cases_unresolved\"])}')
for u in results['cases_unresolved']:
    print(f'  {u[\"case_number\"]}: {u[\"missing_fields\"]}')
"
```

**Step 3: Commit**

```bash
git add scraper/self_diagnosis.py
git commit -m "feat: add main diagnose_and_heal_upset_bids function"
```

---

## Task 6: Integrate into daily_scrape.py

**Files:**
- Modify: `scraper/daily_scrape.py` (around line 405)

**Step 1: Add import**

At top of file with other imports, add:

```python
from scraper.self_diagnosis import diagnose_and_heal_upset_bids
```

**Step 2: Add Task 5 after Task 4**

Find the section after Task 4 (reclassify stale cases) and before the summary section. Add:

```python
        # Task 5: Self-diagnosis and healing
        logger.info("Task 5: Running self-diagnosis for upset_bid cases...")
        try:
            results['self_diagnosis'] = diagnose_and_heal_upset_bids(dry_run)
        except Exception as e:
            logger.error(f"Task 5 (self-diagnosis) failed: {e}")
            results['errors'].append(f"self_diagnosis: {e}")
            results['self_diagnosis'] = {'error': str(e)}
```

**Step 3: Test integration**

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.daily_scrape import run_daily_scrape
# Just verify import works
print('daily_scrape imports self_diagnosis successfully')
"
```

**Step 4: Commit**

```bash
git add scraper/daily_scrape.py
git commit -m "feat: integrate self-diagnosis as Task 5 in daily scrape"
```

---

## Task 7: Test full workflow

**Files:**
- None (testing only)

**Step 1: Run dry-run daily scrape**

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.daily_scrape import run_daily_scrape
from datetime import date
results = run_daily_scrape(target_date=date.today(), dry_run=True)
print('Self-diagnosis results:')
print(results.get('self_diagnosis', 'No self_diagnosis key'))
"
```

**Step 2: Verify self_diagnosis key in results**

Expected output should include:
```
Self-diagnosis results:
{'cases_checked': 37, 'cases_incomplete': 0, ...}
```

**Step 3: Final commit with docs update**

```bash
git add -A
git commit -m "feat: complete self-diagnosis system implementation"
```

---

## Task 8: Handle missing document_downloader (if needed)

**Only do this task if Task 3 Step 2 showed the import fails.**

**Files:**
- Create: `scraper/document_downloader.py`

**Step 1: Create document downloader module**

```python
"""Document download utilities for case healing."""

from typing import List
from database.connection import get_session
from database.models import Case, CaseEvent, Document
from common.logger import setup_logger
import os
import requests

logger = setup_logger(__name__)

DOCUMENTS_DIR = "documents"


def download_case_documents(case_id: int, force: bool = False) -> int:
    """
    Download documents for a case from event URLs.

    Args:
        case_id: Database ID of the case
        force: If True, re-download even if file exists

    Returns:
        Number of documents downloaded
    """
    downloaded = 0

    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            logger.error(f"Case {case_id} not found")
            return 0

        events = session.query(CaseEvent).filter(
            CaseEvent.case_id == case_id,
            CaseEvent.document_url.isnot(None)
        ).all()

        case_dir = os.path.join(DOCUMENTS_DIR, case.county_code, case.case_number)
        os.makedirs(case_dir, exist_ok=True)

        for event in events:
            if not event.document_url:
                continue

            # Generate filename from event
            filename = f"{event.event_date}_{event.event_type[:30]}.pdf".replace("/", "_").replace(" ", "_")
            filepath = os.path.join(case_dir, filename)

            if os.path.exists(filepath) and not force:
                continue

            try:
                response = requests.get(event.document_url, timeout=30)
                response.raise_for_status()

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                # Update or create document record
                doc = session.query(Document).filter_by(
                    case_id=case_id,
                    document_name=filename
                ).first()

                if not doc:
                    doc = Document(
                        case_id=case_id,
                        document_name=filename,
                        file_path=filepath,
                        event_id=event.id
                    )
                    session.add(doc)
                else:
                    doc.file_path = filepath
                    doc.ocr_text = None  # Clear for re-OCR

                downloaded += 1
                logger.info(f"Downloaded: {filepath}")

            except Exception as e:
                logger.error(f"Failed to download {event.document_url}: {e}")

        session.commit()

    return downloaded
```

**Step 2: Test import**

```bash
PYTHONPATH=$(pwd) venv/bin/python -c "
from scraper.document_downloader import download_case_documents
print('document_downloader imported successfully')
"
```

**Step 3: Commit**

```bash
git add scraper/document_downloader.py
git commit -m "feat: add document_downloader module for Tier 2 healing"
```
