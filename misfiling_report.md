# Document Misfiling Investigation Report

## Summary
Investigated all upset_bid cases (49 Report of Sale documents checked) for document misfiling issues where a document attached to one case actually contains data for a different case.

**Key Finding:** 2 confirmed misfilings found (4.1% error rate), but NO DATA CORRUPTION occurred because the extraction system successfully extracted correct data from alternative documents.

## Confirmed Misfilings: 2 Cases

### 1. Case 25SP002519-910 (CONFIRMED MISFILING)
**Problem:** Report of Sale document contains data for case 24SP000376-910

**Details:**
- **Actual Case:** 25SP002519-910
- **Property:** 6709 W. Lake Anne Drive, Raleigh NC 27612
- **Document ID:** 25883
- **Document Name:** 12-09-2025_Report of Sale.pdf
- **OCR Shows:** "24SP000376-910" and "DAVID EUGENE BALLARD"
- **Should Be:** Data for 25SP002519-910

**Verification:**
- All other documents for case 25SP002519-910 correctly show "25SP002519-910"
- Case 24SP000376-910 is a DIFFERENT property: 4416 South Ridge Drive, Fuquay-Varina
- Case 24SP000376-910 has its own correct Report of Sale (doc ID 25823)

**Impact:**
- Current extracted data: Sale date 2025-12-09, Bid $450,000.00
- Bid amount was extracted from OTHER documents (unknown_.pdf, Attorney Fees), NOT from misfiled Report of Sale
- **NO DATA CORRUPTION** - Extraction system successfully used alternative documents

---

### 2. Case 25SP000212-420 (CONFIRMED MISFILING)
**Problem:** Report of Sale document contains data for case 25SP000513-310

**Details:**
- **Actual Case:** 25SP000212-420 (Harnett County)
- **Property:** 1596 McLean Chapel Church Road, Bunnlevel, NC 28323-9646
- **Style:** Ernest Kendrick Elliott
- **Document ID:** 19119
- **Document Name:** 12-04-2025_Report Of Foreclosure Sale Chapter 45.pdf
- **OCR Shows:** "FILE NO. 25SP000513-310" (Durham County)
- **Should Be:** Data for 25SP000212-420

**Verification:**
- Cases are in DIFFERENT counties (420 = Harnett, 310 = Durham)
- Case 25SP000513-310 is for a different person: Ida Delaney, Durham
- Case 25SP000513-310 has its own Report of Sale (doc ID 18919, dated 11-06-2025)

**Impact:**
- Current extracted data: Sale date 2018-06-06 (?), Bid $84,456.91
- Bid amount was extracted from "Upset Bid Filed" documents, NOT from misfiled Report of Sale
- **NO DATA CORRUPTION** - Extraction system successfully used alternative documents
- Sale date 2018-06-06 seems unusual (7 years ago) - may need verification

---

## False Positives (OCR Errors): 3 Cases

### 3. Case 24SP000581-910
- **Document ID:** 19817
- **OCR Shows:** "94SP000581-9" (OCR misread "24" as "94")
- **Status:** OCR error, not a real misfiling

### 4. Case 25SP000357-670
- **Document ID:** 19808
- **OCR Shows:** "95SP000357-660" (OCR misread "25" as "95" and "670" as "660")
- **Status:** OCR error, not a real misfiling

### 5. Case 25SP002123-910
- **Document ID:** 25981
- **OCR Shows:** "25SP00005044f0" (garbled OCR)
- **Status:** OCR error, not a real misfiling

---

## Recommendations

1. **Immediate Action Required:**
   - Manually verify bid amounts and sale dates for cases 25SP002519-910 and 25SP000212-420
   - Check if the correct Report of Sale documents exist elsewhere in the portal
   - Re-run extraction on these cases after obtaining correct documents

2. **Root Cause:**
   - Court clerks may have attached wrong documents when filing
   - Portal may have document attachment errors
   - Need to investigate how these documents were downloaded

3. **Prevention:**
   - Implement automated cross-checking of case numbers in OCR vs. case_number field
   - Add validation during document download to flag mismatches
   - Consider adding this check to daily self-diagnosis system

4. **Data Integrity:**
   - Total cases checked: 49
   - Confirmed misfilings: 2 (4.1% error rate)
   - False positives (OCR errors): 3
   - This suggests other cases may have similar issues that went undetected

---

## SQL Query for Future Checks

```sql
WITH case_numbers_in_docs AS (
    SELECT
        c.case_number as actual_case,
        d.id as doc_id,
        d.document_name,
        substring(c.case_number from '^(\d{2}SP\d{6})') as base_case,
        regexp_matches(d.ocr_text, '(\d{2})\s*[- ]?\s*SP\s*[- ]?\s*0*(\d{6})', 'g') as found_parts
    FROM documents d
    JOIN cases c ON d.case_id = c.id
    WHERE c.classification = 'upset_bid'
      AND d.document_name LIKE '%Report%Sale%'
      AND d.ocr_text IS NOT NULL
      AND LENGTH(d.ocr_text) > 100
)
SELECT DISTINCT
    actual_case,
    doc_id,
    document_name,
    found_parts[1] || 'SP' || found_parts[2] as found_case
FROM case_numbers_in_docs
WHERE found_parts[1] || 'SP' || found_parts[2] <> base_case
ORDER BY actual_case;
```
