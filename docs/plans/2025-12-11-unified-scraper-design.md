# Unified Scraper Design

**Date:** 2025-12-11
**Status:** Approved

## Overview

Consolidate `initial_scrape.py` and `date_range_scrape.py` into a unified scraper architecture using `DateRangeScraper` as the single core, with configurable chunking for batch operations.

## Problem

We have two scraper files doing essentially the same thing:
- `initial_scrape.py` - Single county, historical backfill
- `date_range_scrape.py` - Multi-county, daily scrapes

This causes confusion and maintenance overhead. The only real differences are county selection and date ranges, which should be parameters, not separate codebases.

## Solution

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Entry Points                      │
├─────────────────────────────────────────────────────────┤
│  date_range_scrape.py    - Single search (direct use)   │
│  batch_scrape.py         - Sequential chunked searches  │
│  parallel_scrape.py      - Concurrent chunked searches  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│              DateRangeScraper (core)                    │
│  - Multi-county support (1 CAPTCHA for all)             │
│  - Single-county override                               │
│  - Skipped case logging                                 │
│  - PDF downloading                                      │
└─────────────────────────────────────────────────────────┘
```

### Files After Consolidation

| File | Purpose |
|------|---------|
| `scraper/date_range_scrape.py` | Core scraper (unchanged) |
| `scraper/batch_scrape.py` | Sequential chunked searches (renamed from batch_initial_scrape.py) |
| `scraper/parallel_scrape.py` | Concurrent chunked searches (renamed from parallel_batch_scrape.py) |
| ~~`scraper/initial_scrape.py`~~ | Deleted |

## Chunking Strategy

**Supported chunk sizes:** daily, weekly, monthly, quarterly, yearly

### CLI Interface

**batch_scrape.py:**
```bash
# Historical backfill - monthly chunks, all counties
PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
  --start 2024-01-01 --end 2025-11-24 --chunk monthly

# Single county, quarterly chunks
PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
  --start 2024-01-01 --end 2024-12-31 --chunk quarterly --county wake

# Daily chunks (for recent catch-up)
PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
  --start 2025-12-01 --end 2025-12-10 --chunk daily
```

**parallel_scrape.py:**
```bash
# Same interface, adds --workers flag
PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
  --start 2024-01-01 --end 2025-11-24 --chunk monthly --workers 3
```

### Chunking Utility Function

```python
def generate_date_chunks(start_date, end_date, chunk_size):
    """
    Generate date ranges based on chunk size.

    Args:
        start_date: Start date (date object)
        end_date: End date (date object)
        chunk_size: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'

    Returns:
        List of (chunk_start, chunk_end) tuples
    """
```

## Migration Details

### Code Changes

**OLD (InitialScraper):**
```python
from scraper.initial_scrape import InitialScraper, TruncatedResultsError

scraper = InitialScraper(
    county=county,
    start_date=start_str,
    end_date=end_str,
    test_mode=False,
    limit=None
)
scraper.run()
```

**NEW (DateRangeScraper):**
```python
from scraper.date_range_scrape import DateRangeScraper

scraper = DateRangeScraper(
    start_date=start_str,
    end_date=end_str,
    counties=[county] if county else None,  # None = all 6 counties
    limit=None
)
scraper.run()
```

### Key Differences

| Aspect | InitialScraper | DateRangeScraper |
|--------|---------------|------------------|
| County param | `county="wake"` (single, required) | `counties=["wake"]` (list, optional) |
| Default counties | None (must specify) | All 6 target counties |
| Skipped case logging | No | Yes |
| CAPTCHA efficiency | 1 per county | 1 per search (all counties) |

## Files to Delete

- `scraper/initial_scrape.py` (654 lines)

## Documentation Updates

| File | Change |
|------|--------|
| `docs/TESTING_GUIDE.md` | Replace `initial_scrape.py` examples with `date_range_scrape.py` |
| `docs/SETUP.md` | Update architecture note and example commands |
| `docs/FROOTVPN_SETUP.md` | Update example command |
| `docs/plans/*.md` | Leave as-is (historical planning docs) |
| `CLAUDE.md` | Add note about unified scraper, update Key Commands section |

## Implementation Order

1. Add `generate_date_chunks()` utility function
2. Update `batch_initial_scrape.py` → rename to `batch_scrape.py`, use DateRangeScraper
3. Update `parallel_batch_scrape.py` → rename to `parallel_scrape.py`, use DateRangeScraper
4. Delete `initial_scrape.py`
5. Update documentation
6. Single commit with all changes

## Post-Implementation

Run historical backfill:
```bash
PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
  --start 2024-01-01 --end 2025-11-24 --chunk monthly --workers 3
```
