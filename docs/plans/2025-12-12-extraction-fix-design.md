# Fix Extraction for Monitored Cases

## Problem
When case_monitor.py updates existing cases with new documents:
1. It downloads PDFs and runs OCR
2. But never calls `update_case_with_extracted_data()` to run full extraction
3. Even if it did, bid amounts only fill empty fields - won't update with new higher upset bids

Result: Cases with new Report of Sale or Upset Bid documents don't get their bid amounts populated.

## Evidence
- Case 25SP000633-310 has Report of Sale document with $435,000 in OCR text
- But `cases.current_bid_amount` is NULL
- 10 of 37 upset_bid cases have missing bid amounts

## Solution

### Change 1: Call extraction after monitoring
**File:** `scraper/case_monitor.py`
**Location:** After line 750 (classification update)
**Add:**
```python
# Run full extraction to populate any missing fields from new documents
from extraction.extractor import update_case_with_extracted_data
extraction_updated = update_case_with_extracted_data(case.id)
if extraction_updated:
    logger.info(f"  Extraction updated case data")
    result['extraction_updated'] = True
```

### Change 2: Allow bid amount updates when higher
**File:** `extraction/extractor.py`
**Location:** Around line 1086
**Change from:**
```python
if extracted['current_bid_amount'] and not case.current_bid_amount:
```
**Change to:**
```python
if extracted['current_bid_amount'] and (
    not case.current_bid_amount or
    extracted['current_bid_amount'] > case.current_bid_amount
):
```

Also update the logging to indicate whether it was a new fill or an update.

## Verification
After implementation:
1. Run extraction on case 25SP000633-310
2. Verify bid amount shows $435,000
3. Run on all 10 affected upset_bid cases
4. Verify dashboard shows complete data
