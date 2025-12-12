# Self-Diagnosis System Design

**Date:** 2025-12-12
**Status:** Approved

## Overview

Automatically detect and fix missing data in upset_bid cases after each daily scrape.

- **Trigger:** Runs as Task 5 in `daily_scrape.py`, immediately after stale reclassification
- **Scope:** All cases with `classification = 'upset_bid'` (~37 cases)

## Required Fields

For an upset_bid case to be "complete":

| Field | Source |
|-------|--------|
| `case_number` | Case portal |
| `property_address` | Extracted from PDF (Notice of Sale, Deed of Trust) |
| `current_bid_amount` | Extracted from Report of Sale PDF |
| `minimum_next_bid` | Calculated as `current_bid * 1.05` or extracted |
| `next_bid_deadline` | Calculated from sale event date + 10 business days |
| `sale_date` | From sale event in case_events |

## Tiered Self-Healing Strategy

1. **Tier 1: Re-extract** - Re-run extraction on existing documents (fast, no network)
2. **Tier 2: Re-download + extract** - Download documents again, then extract
3. **Tier 3: Full re-scrape** - Visit case URL, re-parse events, download docs, extract

**Exit Condition:** Stop as soon as all required fields are populated.

## Implementation

**New File:** `scraper/self_diagnosis.py`

**Main Function:**

```python
def diagnose_and_heal_upset_bids() -> dict:
    """
    Check all upset_bid cases for completeness and attempt self-healing.

    Returns:
        {
            'cases_checked': int,
            'cases_incomplete': int,
            'cases_healed': int,
            'cases_unresolved': [{'case_id': int, 'case_number': str, 'missing_fields': [...]}],
            'healing_attempts': {
                'tier1_reextract': {'attempted': int, 'succeeded': int},
                'tier2_redownload': {'attempted': int, 'succeeded': int},
                'tier3_rescrape': {'attempted': int, 'succeeded': int}
            }
        }
    """
```

**Integration:** Add as Task 5 in `daily_scrape.py`

**Helper Functions:**
- `_check_completeness(case) -> list[str]` - Returns list of missing field names
- `_tier1_reextract(case) -> bool` - Re-run extraction on existing docs
- `_tier2_redownload(case) -> bool` - Re-download docs, then extract
- `_tier3_rescrape(case) -> bool` - Full case re-scrape via CaseMonitor

## Logic Flow

```
diagnose_and_heal_upset_bids()
    │
    ├─► Query all cases WHERE classification = 'upset_bid'
    │
    ├─► For each case:
    │       │
    │       ├─► missing = _check_completeness(case)
    │       │
    │       ├─► If missing is empty → skip (already complete)
    │       │
    │       ├─► Tier 1: _tier1_reextract(case)
    │       │       └─► Re-check completeness → if complete, continue to next case
    │       │
    │       ├─► Tier 2: _tier2_redownload(case)
    │       │       └─► Re-check completeness → if complete, continue to next case
    │       │
    │       ├─► Tier 3: _tier3_rescrape(case)
    │       │       └─► Re-check completeness → if complete, continue to next case
    │       │
    │       └─► Still incomplete → add to unresolved list
    │
    └─► Return summary dict
```

## Tier Details

**Tier 1: Re-extract**
- Query existing documents for the case from `documents` table
- Call `update_case_with_extracted_data(case_id)` from `extraction/extractor.py`
- Re-runs all extraction patterns against existing `ocr_text`
- Why it might work: Extraction patterns may have been updated since original scrape

**Tier 2: Re-download + Extract**
- Get case events that have document URLs
- Re-download PDFs using existing download logic
- Run OCR on fresh downloads via `process_documents_for_case()`
- Call `update_case_with_extracted_data(case_id)`
- Why it might work: Original download may have failed silently, or PDF was updated

**Tier 3: Full Re-scrape**
- Use `CaseMonitor` to visit the case URL directly
- Re-parse all events from the page
- Download any new documents found
- Run OCR and extraction
- Why it might work: Events may have been missed, or new documents filed since last scrape

## Output Format

**Return Dict:**

```python
'self_diagnosis': {
    'cases_checked': 37,
    'cases_incomplete': 3,
    'cases_healed': 2,
    'cases_unresolved': [
        {
            'case_id': 1234,
            'case_number': '25SP001234-910',
            'missing_fields': ['property_address']
        }
    ],
    'healing_attempts': {
        'tier1_reextract': {'attempted': 3, 'succeeded': 1},
        'tier2_redownload': {'attempted': 2, 'succeeded': 1},
        'tier3_rescrape': {'attempted': 1, 'succeeded': 0}
    }
}
```

**Logging:**
```
INFO: Self-diagnosis: checking 37 upset_bid cases
INFO: Case 25SP001234-910: missing ['current_bid_amount', 'property_address']
INFO: Case 25SP001234-910: Tier 1 (re-extract) - attempting...
INFO: Case 25SP001234-910: Tier 1 - healed current_bid_amount, still missing ['property_address']
INFO: Case 25SP001234-910: Tier 2 (re-download) - attempting...
INFO: Case 25SP001234-910: Tier 2 - complete, all fields populated
INFO: Self-diagnosis complete: 3 incomplete, 2 healed, 1 unresolved
```

## Existing Code to Reuse

- `extraction/extractor.py` → `update_case_with_extracted_data()`
- `scraper/case_monitor.py` → `CaseMonitor.monitor_case()`
- `ocr/processor.py` → `process_documents_for_case()`
