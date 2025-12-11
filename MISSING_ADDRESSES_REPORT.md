# Missing Addresses Report - Dec 11, 2025

## Summary

Found **2 upset_bid cases** with missing property addresses. Both are from the Dec 10, 2025 scrape.

## Cases with Missing Addresses

### 1. Case 24SP002605-910 (Wake County)
- **Case Number:** 24SP002605-910
- **County:** Wake
- **Classification:** upset_bid
- **Sale Date:** 2025-12-10
- **Next Bid Deadline:** 2025-12-22
- **Current Bid Amount:** MISSING
- **Property Address:** MISSING
- **Case URL:** https://portal-nc.tylertech.cloud/app/RegisterOfActions/#/EA167CFF7A47A1770A00A460ABAA890745E26EE801140F6E34416DB7E353824322CD8F46D712EA98B5CF3D63567E8E8CD7BD61BAB54A44F90CC851C1955DFC66A45549DD330804B1509E10EDAB473CF4/anon/portalembed

**Documents Currently Stored:**
- `24SP002605-910.pdf` (Cover Sheet only - no property address)
  - OCR: Yes (9,744 chars)
  - Contains: Attorney information (Brock & Scott, PLLC, 5431 Oleander Drive, Wilmington, NC 28403)

**Sale-Related Events:**
- 2025-12-10: Report Of Foreclosure Sale (Chapter 45) - **NOT DOWNLOADED**
- 2025-09-25: Notice Of Sale/Resale

**Status:** Need to download "Report Of Foreclosure Sale" document from court website

---

### 2. Case 25SP000419-310 (Durham County)
- **Case Number:** 25SP000419-310
- **County:** Durham
- **Classification:** upset_bid
- **Sale Date:** 2025-12-10
- **Next Bid Deadline:** 2025-12-22
- **Current Bid Amount:** MISSING
- **Property Address:** MISSING
- **Case URL:** https://portal-nc.tylertech.cloud/app/RegisterOfActions/#/ECAF2C347B2BAB1B5EC162FE3A57A32A637F98B8BA3A4361BF09528901D4BFE436B371BD88D24375296F8BA6C5DDBEE3224E1CC9ACC95DA089BF51AE5DEE55F1ADB6C0031768CDC50B6BF7C5541E8594/anon/portalembed

**Documents Currently Stored:**
- `25SP000419-310.pdf` (Cover Sheet only - no property address)
  - OCR: Yes (10,142 chars)
  - Contains: Attorney information (Brock & Scott, PLLC, 5431 Oleander Drive, Wilmington, NC 28403)

**Sale-Related Events:**
- 2025-12-10: Report Of Foreclosure Sale (Chapter 45) - **NOT DOWNLOADED**
- 2025-11-13: NOTICE OF FORECLOSURE SALE
- 2025-11-13: Notice Of Sale/Resale

**Status:** Need to download "Report Of Foreclosure Sale" document from court website

---

## Root Cause Analysis

### Why Are Addresses Missing?

1. **Only Cover Sheets Downloaded:** The scraper only downloaded the initial cover sheet PDFs for these cases
2. **Cover Sheets Don't Contain Property Info:** Cover sheets only contain case metadata and attorney information
3. **Sale Documents Not Downloaded:** The "Report Of Foreclosure Sale" documents (filed Dec 10) contain the property addresses and bid amounts but were not downloaded
4. **No Document URLs in Events:** The `document_url` field is NULL for these sale events, preventing automated download

### Why Did OCR Extraction Fail?

The address extraction script (`extract_property_address()`) correctly identified that no property address exists in the cover sheet OCR text. The only address found was the attorney's office address (5431 Oleander Drive, Wilmington, NC 28403).

---

## Recommended Actions

### Immediate Actions (Manual)

1. **Visit the case URLs** and manually download the "Report Of Foreclosure Sale" documents:
   - Wake 24SP002605-910: Navigate to case URL → Find Dec 10 "Report Of Foreclosure Sale" → Download
   - Durham 25SP000419-310: Navigate to case URL → Find Dec 10 "Report Of Foreclosure Sale" → Download

2. **Run OCR on Downloaded Documents:**
   ```bash
   PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/ocr_report_of_sale_docs.py
   ```

3. **Extract Addresses:**
   ```bash
   PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/fix_missing_addresses.py
   ```

### Longer-Term Fix (Automated)

1. **Enhance Document Download Logic:**
   - Modify scraper to identify and download "Report Of Foreclosure Sale" documents for upset_bid cases
   - Add logic to detect when sale events occur and trigger document downloads
   - Implement retry logic for cases with missing addresses

2. **Add Validation Step:**
   - After classifying cases as upset_bid, validate that property_address and current_bid_amount are populated
   - If missing, log warning and attempt to re-download sale documents

3. **Consider Case Monitor Enhancement:**
   - The `case_monitor.py` script could check for new sale documents and download them automatically
   - Add to daily scrape workflow: "Check upset_bid cases for missing addresses/bid amounts"

---

## Technical Details

### Database Schema
- **Cases Table:** `property_address` field is NULL for these 2 cases
- **Documents Table:** Only cover sheet PDFs stored
- **Events Table:** Sale events exist but `document_url` is NULL

### Address Extraction Patterns
The `extract_property_address()` function looks for patterns like:
- "Property Address: 123 Main St"
- "[address] City North Carolina 27613"
- Affidavit patterns with addresses
- Report of Sale patterns

These patterns were not found in the cover sheets (as expected).

### Files Used
- `/home/ahn/projects/nc_foreclosures/scripts/fix_missing_addresses.py` - Address extraction script
- `/home/ahn/projects/nc_foreclosures/extraction/extractor.py` - `extract_property_address()` function
- `/home/ahn/projects/nc_foreclosures/ocr/processor.py` - `process_document()` function
- `/home/ahn/projects/nc_foreclosures/scripts/ocr_report_of_sale_docs.py` - Bulk OCR script for sale documents

---

## Next Steps

1. **User Decision Required:** Should we manually download the sale documents, or build automated scraper enhancement first?

2. **If Manual:** Navigate to case URLs and download "Report Of Foreclosure Sale" PDFs

3. **If Automated:** Modify scraper to detect and download sale documents for upset_bid cases

---

*Report generated: 2025-12-11*
