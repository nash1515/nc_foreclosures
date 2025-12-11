# Missing Bid Amounts - Final Report

**Date:** December 9, 2025
**Task:** Fix missing `current_bid_amount` for upset_bid cases on Dashboard

## Summary

- **Initial count:** 8 upset_bid cases missing bid amounts
- **Fixed:** 3 cases
- **Remaining:** 5 cases still need attention

## Progress

### Fixed Cases

1. **Case ID 813** - 24SP000581-910 (Wake) - Fixed by case_monitor
2. **Case ID 1271** - 25SP000397-420 (Harnett) - Fixed by case_monitor
3. **Case ID 1057** - 25SP000357-670 (Orange) - Fixed by extraction script v2
   - Current bid: $95,000.00
   - Minimum next: $99,750.00
   - Method: Calculated from "Minimum Amount Of Next Upset Bid" field

### Still Need Attention (5 cases)

| Case Number | Case ID | County | Deadline | Issue |
|-------------|---------|--------|----------|-------|
| 24SP001996-910 | 932 | Wake | 2025-12-18 | Report of Sale doc exists but extraction failing |
| 25SP000089-180 | 1006 | Chatham | 2025-12-18 | Multiple docs identified as Report of Sale, none have bid info |
| 25SP001017-910 | 1467 | Wake | 2025-12-18 | Report of Sale doc exists but extraction failing |
| 25SP001024-910 | 1469 | Wake | 2025-12-18 | Some docs have upset bid indicators, extraction failing |
| 25SP001706-910 | 1598 | Wake | 2025-12-15 | No Report of Sale document found |

## Root Causes

### 1. Document Download Issues
- Some cases have the "Report Of Foreclosure Sale" event recorded, but the actual PDF hasn't been downloaded yet
- Solution: Run case_monitor more frequently or implement document watching

### 2. OCR Quality Issues
- The "Amount Of Bid" field in Report of Sale documents is often handwritten
- OCR struggles with handwritten amounts (e.g., "$05000" instead of "$105,000")
- Our solution: Use the typed "Minimum Amount Of Next Upset Bid" field and calculate backwards (÷ 1.05)

### 3. Document Misclassification
- Some documents are being flagged as "Report of Sale" when they're actually other document types
- The `is_report_of_sale_document()` function may be too permissive

## What Was Done

### 1. Diagnostic Analysis
- Created `/home/ahn/projects/nc_foreclosures/scripts/diagnostic_report.py`
- Identified that Report of Sale documents were missing from the database

### 2. Document Download
- Ran `case_monitor.py --classification upset_bid`
- Downloaded new documents for all upset_bid cases
- Added 70+ documents for case 813 alone

### 3. OCR Processing
- Created `/home/ahn/projects/nc_foreclosures/scripts/ocr_report_of_sale_docs.py`
- Processed Report of Sale documents through OCR
- Note: Some documents already had OCR from the case_monitor run

### 4. Improved Extraction
- Created `/home/ahn/projects/nc_foreclosures/scripts/fix_missing_bid_amounts_v2.py`
- New approach: Extract "Minimum Amount Of Next Upset Bid" instead of handwritten "Amount Of Bid"
- Calculate current_bid = minimum_next / 1.05 (NC law requires 5% increase)

## Recommendations

### Short-term (Manual Fix)

For the remaining 5 cases, manually check the county website:

```bash
# Check database for case URLs
PYTHONPATH=$(pwd) venv/bin/python -c "
from database.connection import get_session
from database.models import Case

with get_session() as session:
    for case_id in [932, 1006, 1467, 1469, 1598]:
        case = session.query(Case).filter_by(id=case_id).first()
        print(f'{case.case_number}: {case.case_url}')
"
```

Visit each URL and find the Report of Foreclosure Sale document to get the bid amount.

### Medium-term (Automation)

1. **Enhance is_report_of_sale_document()** in `/home/ahn/projects/nc_foreclosures/extraction/extractor.py`
   - Make it more strict to avoid false positives
   - Require presence of "AOC-SP-301" form number or "REPORT OF FORECLOSURE SALE" title

2. **Add fallback extraction patterns**
   - Handle more OCR variations (missing digits, split amounts, etc.)
   - Try multiple extraction methods before giving up

3. **Monitor document downloads**
   - Add a check in case_monitor to verify Report of Sale docs were actually downloaded
   - Alert if a case has a sale_date but no corresponding document

### Long-term (Prevention)

1. **Dashboard UX improvement**
   - Show "Bid Amount: TBD" or "Pending" for cases without bid_amount
   - Add a "needs review" flag for cases classified as upset_bid without bid amounts

2. **Automated re-scraping**
   - If a case transitions to upset_bid but bid_amount is NULL after 24 hours, flag for re-scraping
   - Implement document watching to detect when new docs are filed

3. **Manual entry interface**
   - Add a simple form in the web app to manually enter bid amounts when OCR fails
   - Store source/timestamp for audit trail

## Scripts Created

1. `/home/ahn/projects/nc_foreclosures/scripts/diagnostic_report.py` - Analyze why bid amounts are missing
2. `/home/ahn/projects/nc_foreclosures/scripts/fix_missing_bid_amounts.py` - Original extraction attempt
3. `/home/ahn/projects/nc_foreclosures/scripts/fix_missing_bid_amounts_v2.py` - Improved extraction using Minimum Next Upset
4. `/home/ahn/projects/nc_foreclosures/scripts/ocr_report_of_sale_docs.py` - OCR specific documents

## Key Learnings

1. **Trust the typed fields over handwritten** - NC court clerks type the "Minimum Amount Of Next Upset Bid" field, which is much more reliable than OCR'ing handwritten bid amounts

2. **Document downloads happen asynchronously** - Just because an event says "Report Of Foreclosure Sale" doesn't mean the document has been downloaded yet

3. **Classification ≠ Data completeness** - A case can be correctly classified as "upset_bid" even if we don't have the bid amount yet

4. **The 1.05 rule is your friend** - NC law requires upset bids to be 5% higher, so any field showing the minimum next bid can be used to calculate the current bid

## Next Steps

1. Manually fix the remaining 5 cases by visiting county websites
2. Update the extraction patterns in `extraction/extractor.py` to handle more OCR variations
3. Consider adding a "data quality" field to track cases with incomplete information
4. Schedule case_monitor to run more frequently (currently 5 AM daily, maybe add noon run?)
