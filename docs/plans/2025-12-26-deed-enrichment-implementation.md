# Deed Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deed book/page extraction guidance and county-specific deed URL links to the NC Foreclosures system.

**Architecture:** Enhance AI prompt to distinguish Deed Book from Book of Maps, then route deed URL generation through county-specific builders similar to RE enrichment. Store URLs in existing `enrichments.deed_url` column.

**Tech Stack:** Python, Flask API, React/Ant Design, Playwright (Durham only)

---

## Task 1: Enhance AI Prompt for Deed Extraction

**Files:**
- Modify: `analysis/prompt_builder.py:218-219`

**Step 1: Add deed extraction guidance section**

In `analysis/prompt_builder.py`, find line ~240 (after RED FLAGS section) and add this guidance block. Add it to the prompt string around line 240, before the closing `"""`:

```python
## DEED BOOK vs BOOK OF MAPS/PLAT BOOK
- **Deed Book**: Records property ownership transfers and deeds of trust (mortgages). This is what we need.
- **Book of Maps** (Wake County) / **Plat Book** (other counties): Records subdivision plat maps showing lot boundaries. Do NOT extract these.
- Example Deed reference: "recorded in Deed Book 15704, Page 1495" - EXTRACT THIS
- Example Plat reference: "as shown on map recorded in Book of Maps 2007, Page 1270" - IGNORE THIS
- Look for the deed of trust that secures the loan being foreclosed.
```

**Step 2: Update JSON schema descriptions**

Replace lines 218-219:
```python
  "deed_book": "<deed book number if found, or null>",
  "deed_page": "<deed page number if found, or null>",
```

With:
```python
  "deed_book": "<Deed Book number for the property's deed of trust - NOT Book of Maps or Plat Book>",
  "deed_page": "<Deed Page number corresponding to the Deed Book above>",
```

**Step 3: Verify changes**

Run: `python -c "from analysis.prompt_builder import build_analysis_prompt; print('OK')"`
Expected: `OK` (no import errors)

**Step 4: Commit**

```bash
git add analysis/prompt_builder.py
git commit -m "feat: enhance AI prompt to distinguish Deed Book from Book of Maps"
```

---

## Task 2: Create Deed URL Builders Module

**Files:**
- Create: `enrichments/deed/__init__.py`
- Create: `enrichments/deed/router.py`
- Create: `enrichments/deed/url_builders.py`

**Step 1: Create module directory and __init__.py**

```bash
mkdir -p enrichments/deed
```

Create `enrichments/deed/__init__.py`:
```python
"""Deed enrichment module - generates county-specific deed lookup URLs."""

from enrichments.deed.router import build_deed_url, enrich_deed

__all__ = ['build_deed_url', 'enrich_deed']
```

**Step 2: Create URL builders**

Create `enrichments/deed/url_builders.py`:
```python
"""County-specific deed URL builders."""


def build_wake_url(deed_book: str, deed_page: str) -> str:
    """Wake County - Direct link via new CRPI system."""
    return (
        f"https://rodrecords.wake.gov/web/web/integration/search"
        f"?field_BookPageID_DOT_Volume={deed_book}"
        f"&field_BookPageID_DOT_Page={deed_page}"
    )


def build_durham_url() -> str:
    """Durham County - Search page only (requires Playwright for direct link)."""
    return "https://rodweb.dconc.gov/web/search/DOCSEARCH5S1"


def build_harnett_url(deed_book: str, deed_page: str) -> str:
    """Harnett County - Direct link via Courthouse Computer Systems."""
    return (
        f"https://us6.courthousecomputersystems.com/HarnettNC/Image/ShowDocImage"
        f"?booktype=Deed&tif2pdf=true&BookNum={deed_book}&PageNum={deed_page}"
    )


def build_orange_url(deed_book: str, deed_page: str) -> str:
    """Orange County - Direct link via Courthouse Computer Systems."""
    return (
        f"https://rod.orangecountync.gov/orangenc/Image/ShowDocImage"
        f"?booktype=Deed&tif2pdf=true&BookNum={deed_book}&PageNum={deed_page}"
    )


def build_lee_url() -> str:
    """Lee County - Search page only (Logan Systems, user clicks Book/Page tab)."""
    return "https://www.leencrod.org/search.wgx"


def build_chatham_url() -> str:
    """Chatham County - Search page only (Logan Systems, user clicks Book/Page tab)."""
    return "https://www.chathamncrod.org/search.wgx"
```

**Step 3: Create router**

Create `enrichments/deed/router.py`:
```python
"""
Deed enrichment router.

Routes deed URL generation to county-specific builders based on case number suffix.
"""

import logging
from datetime import datetime

from database.connection import get_session
from database.models import Case
from enrichments.common.models import Enrichment
from enrichments.deed.url_builders import (
    build_wake_url,
    build_durham_url,
    build_harnett_url,
    build_orange_url,
    build_lee_url,
    build_chatham_url,
)

logger = logging.getLogger(__name__)

# County codes
COUNTY_CODES = {
    '910': 'Wake',
    '310': 'Durham',
    '420': 'Harnett',
    '520': 'Lee',
    '670': 'Orange',
    '180': 'Chatham',
}


def build_deed_url(case_number: str, deed_book: str, deed_page: str) -> str | None:
    """
    Build deed URL for the given case.

    Args:
        case_number: Case number with county suffix (e.g., "25SP001234-910")
        deed_book: Deed book number from AI extraction
        deed_page: Deed page number from AI extraction

    Returns:
        URL string or None if inputs invalid
    """
    if not deed_book or not deed_page:
        return None

    if '-' not in case_number:
        logger.warning(f"Invalid case number format: {case_number}")
        return None

    county_code = case_number.split('-')[-1]

    if county_code == '910':  # Wake
        return build_wake_url(deed_book, deed_page)
    elif county_code == '310':  # Durham - search page only
        return build_durham_url()
    elif county_code == '420':  # Harnett
        return build_harnett_url(deed_book, deed_page)
    elif county_code == '520':  # Lee - search page only
        return build_lee_url()
    elif county_code == '670':  # Orange
        return build_orange_url(deed_book, deed_page)
    elif county_code == '180':  # Chatham - search page only
        return build_chatham_url()
    else:
        logger.warning(f"Unknown county code: {county_code}")
        return None


def enrich_deed(case_id: int, deed_book: str, deed_page: str) -> dict:
    """
    Generate and store deed URL for a case.

    Args:
        case_id: Database case ID
        deed_book: Deed book number
        deed_page: Deed page number

    Returns:
        dict with success status and url or error
    """
    with get_session() as session:
        case = session.get(Case, case_id)
        if not case:
            return {'success': False, 'error': 'Case not found'}

        # Build URL
        url = build_deed_url(case.case_number, deed_book, deed_page)
        if not url:
            return {'success': False, 'error': 'Could not build deed URL'}

        # Get or create enrichment record
        enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
        if not enrichment:
            enrichment = Enrichment(case_id=case_id)
            session.add(enrichment)

        # Store URL
        enrichment.deed_url = url
        enrichment.deed_enriched_at = datetime.now()
        enrichment.deed_error = None

        session.commit()
        logger.info(f"Deed enrichment complete for case_id={case_id}: {url}")

        return {'success': True, 'url': url}
```

**Step 4: Verify module imports**

Run: `PYTHONPATH=$(pwd) python -c "from enrichments.deed import build_deed_url, enrich_deed; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add enrichments/deed/
git commit -m "feat: add deed URL builders for all 6 counties"
```

---

## Task 3: Integrate Deed Enrichment with AI Analysis

**Files:**
- Modify: `analysis/analyzer.py:168-172`

**Step 1: Add deed enrichment trigger after analysis completes**

In `analyzer.py`, after line 170 (`analysis.error_message = None`) and before `session.commit()` on line 172, add:

```python
            # Trigger deed enrichment if book/page extracted
            if analysis.deed_book and analysis.deed_page:
                try:
                    from enrichments.deed import enrich_deed
                    deed_result = enrich_deed(case_id, analysis.deed_book, analysis.deed_page)
                    if deed_result.get('success'):
                        logger.info(f"Deed URL generated for case_id={case_id}")
                    else:
                        logger.warning(f"Deed enrichment failed for case_id={case_id}: {deed_result.get('error')}")
                except Exception as e:
                    logger.error(f"Deed enrichment error for case_id={case_id}: {e}")
```

**Step 2: Verify integration**

Run: `PYTHONPATH=$(pwd) python -c "from analysis.analyzer import analyze_case; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add analysis/analyzer.py
git commit -m "feat: trigger deed enrichment after AI analysis extracts book/page"
```

---

## Task 4: Update API to Return Deed URL

**Files:**
- Modify: `web_app/api/cases.py:507-512`

**Step 1: Add deed_url to upset-bids endpoint**

In `web_app/api/cases.py`, find the upset-bids endpoint response (around line 512). After `'chatham_re_url': enrichment.chatham_re_url if enrichment else None`, add:

```python
                'deed_url': enrichment.deed_url if enrichment else None
```

The full block should look like:
```python
                'wake_re_url': enrichment.wake_re_url if enrichment else None,
                'durham_re_url': enrichment.durham_re_url if enrichment else None,
                'harnett_re_url': enrichment.harnett_re_url if enrichment else None,
                'lee_re_url': enrichment.lee_re_url if enrichment else None,
                'orange_re_url': enrichment.orange_re_url if enrichment else None,
                'chatham_re_url': enrichment.chatham_re_url if enrichment else None,
                'deed_url': enrichment.deed_url if enrichment else None
```

**Step 2: Verify API change**

Restart Flask server and test:
```bash
curl -s http://localhost:5001/api/cases/upset-bids | python -c "import sys,json; d=json.load(sys.stdin); print('deed_url' in str(d))"
```
Expected: `True`

**Step 3: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: return deed_url in upset-bids API response"
```

---

## Task 5: Update Dashboard to Show Deed Link

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx:293-297`

**Step 1: Enable deed icon when deed_url exists**

In `Dashboard.jsx`, find lines 293-297 (the disabled Deed tooltip). Replace:

```jsx
            <Tooltip title="Deed - Coming soon">
              <span style={{ cursor: 'not-allowed', opacity: 0.4, display: 'inline-flex', alignItems: 'center' }}>
                <FileTextOutlined style={{ fontSize: 16 }} />
              </span>
            </Tooltip>
```

With:
```jsx
            <Tooltip title={record.deed_url ? "View Deed Record" : "Deed - Coming soon"}>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  if (record.deed_url) window.open(record.deed_url, '_blank');
                }}
                style={{
                  cursor: record.deed_url ? 'pointer' : 'not-allowed',
                  opacity: record.deed_url ? 1 : 0.4,
                  display: 'inline-flex',
                  alignItems: 'center'
                }}
              >
                <FileTextOutlined style={{ fontSize: 16 }} />
              </span>
            </Tooltip>
```

**Step 2: Verify in browser**

Open http://localhost:5174 and check Dashboard Links column. Cases with deed_url should have clickable deed icon.

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx
git commit -m "feat: enable deed link icon on Dashboard when deed_url exists"
```

---

## Task 6: Update Case Detail Quick Links

**Files:**
- Modify: `frontend/src/pages/CaseDetail.jsx:305`

**Step 1: Enable Deed button when deed_url exists**

In `CaseDetail.jsx`, find line 305 (disabled Deed button). Replace:

```jsx
                  <Button size="small" icon={<FileTextOutlined />} disabled>Deed</Button>
```

With:
```jsx
                  {c.deed_url ? (
                    <a href={c.deed_url} target="_blank" rel="noopener noreferrer">
                      <Button size="small" icon={<FileTextOutlined />}>
                        Deed
                      </Button>
                    </a>
                  ) : (
                    <Button size="small" icon={<FileTextOutlined />} disabled>Deed</Button>
                  )}
```

**Step 2: Verify Case Detail page shows deed link**

Open a case with deed_url and verify Deed button is clickable.

**Step 3: Commit**

```bash
git add frontend/src/pages/CaseDetail.jsx
git commit -m "feat: enable Deed button in Case Detail Quick Links"
```

---

## Task 7: Add deed_url to Case Detail API Response

**Files:**
- Modify: `web_app/api/cases.py` (GET single case endpoint)

**Step 1: Find the single case GET endpoint and add deed_url**

Search for the GET endpoint that returns a single case (around line 279). Ensure `deed_url` is included in the response alongside other enrichment URLs.

Find where `wake_re_url`, `durham_re_url`, etc. are returned for a single case and add:
```python
'deed_url': enrichment.deed_url if enrichment else None,
```

**Step 2: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: return deed_url in single case API response"
```

---

## Task 8: Create Backfill Script

**Files:**
- Create: `scripts/backfill_deed_urls.py`

**Step 1: Create backfill script**

Create `scripts/backfill_deed_urls.py`:
```python
#!/usr/bin/env python
"""
Backfill deed URLs for cases that have deed_book/deed_page from AI analysis
but haven't had deed enrichment run yet.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_session
from database.models import CaseAnalysis, Case
from enrichments.common.models import Enrichment
from enrichments.deed import enrich_deed

def backfill_deed_urls(dry_run: bool = True):
    """
    Find cases with deed_book/deed_page but no deed_url and generate URLs.

    Args:
        dry_run: If True, only report what would be done
    """
    with get_session() as session:
        # Find analyses with deed info
        analyses = session.query(CaseAnalysis).filter(
            CaseAnalysis.deed_book.isnot(None),
            CaseAnalysis.deed_page.isnot(None),
            CaseAnalysis.status == 'completed'
        ).all()

        print(f"Found {len(analyses)} cases with deed_book/deed_page")

        updated = 0
        skipped = 0

        for analysis in analyses:
            # Check if enrichment already has deed_url
            enrichment = session.query(Enrichment).filter_by(
                case_id=analysis.case_id
            ).first()

            if enrichment and enrichment.deed_url:
                skipped += 1
                continue

            case = session.get(Case, analysis.case_id)
            if not case:
                print(f"  WARN: Case {analysis.case_id} not found")
                continue

            print(f"  {case.case_number}: book={analysis.deed_book}, page={analysis.deed_page}")

            if not dry_run:
                result = enrich_deed(analysis.case_id, analysis.deed_book, analysis.deed_page)
                if result.get('success'):
                    print(f"    -> {result['url']}")
                    updated += 1
                else:
                    print(f"    -> ERROR: {result.get('error')}")
            else:
                updated += 1

        print(f"\n{'Would update' if dry_run else 'Updated'}: {updated}")
        print(f"Skipped (already have deed_url): {skipped}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backfill deed URLs')
    parser.add_argument('--execute', action='store_true', help='Actually run updates (default is dry run)')
    args = parser.parse_args()

    backfill_deed_urls(dry_run=not args.execute)
```

**Step 2: Test dry run**

Run: `PYTHONPATH=$(pwd) python scripts/backfill_deed_urls.py`
Expected: Lists cases with deed info that would be updated

**Step 3: Execute backfill**

Run: `PYTHONPATH=$(pwd) python scripts/backfill_deed_urls.py --execute`
Expected: Updates enrichments table with deed URLs

**Step 4: Commit**

```bash
git add scripts/backfill_deed_urls.py
git commit -m "feat: add backfill script for deed URLs"
```

---

## Task 9: End-to-End Verification

**Step 1: Verify backfill worked**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT c.case_number, ca.deed_book, ca.deed_page, e.deed_url
FROM case_analyses ca
JOIN cases c ON ca.case_id = c.id
LEFT JOIN enrichments e ON c.id = e.case_id
WHERE ca.deed_book IS NOT NULL
LIMIT 10;
"
```

**Step 2: Verify Dashboard**

Open http://localhost:5174 - check that cases with deed_url have active deed icons.

**Step 3: Verify Case Detail**

Click into a case with deed_url - verify Deed button is active and opens correct URL.

**Step 4: Test each county URL format**

Manually click deed links for:
- Wake County case - should go to direct search result
- Harnett County case - should show deed document directly
- Orange County case - should show deed document directly
- Durham County case - should go to search page
- Lee County case - should go to search page
- Chatham County case - should go to search page

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Enhance AI prompt | `analysis/prompt_builder.py` |
| 2 | Create deed URL builders | `enrichments/deed/` (3 files) |
| 3 | Integrate with AI analysis | `analysis/analyzer.py` |
| 4 | Update upset-bids API | `web_app/api/cases.py` |
| 5 | Update Dashboard UI | `frontend/src/pages/Dashboard.jsx` |
| 6 | Update Case Detail UI | `frontend/src/pages/CaseDetail.jsx` |
| 7 | Update single case API | `web_app/api/cases.py` |
| 8 | Create backfill script | `scripts/backfill_deed_urls.py` |
| 9 | End-to-end verification | N/A |

**Total new files:** 4
**Total modified files:** 4
**Database migration:** None needed (deed_url column exists)
