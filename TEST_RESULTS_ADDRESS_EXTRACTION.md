# Address Extraction Pattern Test Results

**Date:** December 6, 2025
**Test Script:** `/home/ahn/projects/nc_foreclosures/scripts/test_address_extraction.py`

## Summary

Both test cases **PASSED** successfully:

1. ✅ **Case 25SP001154-910** - HOA lien address correctly extracted
2. ✅ **Case 25SP000628-310** - Attorney address correctly rejected

## Test Case 1: 25SP001154-910 (Wake County)

### Status: ✅ SUCCESS

**Expected Behavior:** Extract HOA lien address from "assessments upon ADDRESS" pattern

**OCR Text Pattern Found:**
```
assessments upon 4317 Scaup Court Raleigh, NC, 27616, being known as Lot 96,
Mallard Crossing Subdivision, Phase II...
```

**Extracted Address:**
```
4317 Scaup Court Raleigh, NC, 27616
```

**Results:**
- ✅ Address successfully extracted from 23 documents
- ✅ Pattern matched: "assessments upon ADDRESS"
- ✅ Address format cleaned and normalized correctly
- ✅ No false positives from attorney/law firm addresses

**Database Status:**
- Current DB value: `NULL` (not yet updated)
- Recommended action: Run extraction/re-extraction to populate

---

## Test Case 2: 25SP000628-310 (Durham County)

### Status: ✅ SUCCESS

**Expected Behavior:** Reject attorney address from summons document

**OCR Text Pattern Found:**
```
c/o Brock & Scott, PLLC
Summons Submitted
5431 Oleander Drive
Lives oNo Wilmington, NC 28403
```

**Extracted Address:**
```
None (correctly rejected)
```

**Results:**
- ✅ Attorney address correctly filtered out
- ✅ No false property address extracted
- ✅ Filtering logic working: detected "Brock & Scott, PLLC" context
- ⚠️ No actual property address found in any of the 24 documents

**Database Status:**
- Current DB value: `5431 Oleander Drive, Lives oNo Wilmington, NC 28403` (WRONG - attorney address)
- Recommended action: Clear this field and re-run extraction (should set to NULL)

**Analysis:**
The OCR text only contains the attorney's office address from the summons form. The actual property address may be:
- In a document that wasn't downloaded/OCR'd
- In the deed of trust (not yet downloaded)
- In a legal description without a street address
- Missing from the available documents

---

## Pattern Validation

### New Patterns Added (Working)
1. ✅ `r'assessments?\s+upon\s+([^,]+,\s*[^,]+,\s*NC\s*,?\s*\d{5})'`
   - Matches: "assessments upon ADDRESS"
   - Tested on: Case 25SP001154-910

2. ✅ `r'lien\s+upon\s+([^,]+,\s*[^,]+,\s*NC\s*,?\s*\d{5})'`
   - Matches: "lien upon ADDRESS"
   - Not yet tested (no cases in sample with this pattern)

### Attorney Address Filtering (Working)
- ✅ Detects law firm names: "PLLC", "LLC", "P.A.", "LLP", "Esq"
- ✅ Detects attorney-related terms: "attorney", "law office", "counsel"
- ✅ Returns `None` when attorney context detected
- ✅ Prevents false positives from legal correspondence

---

## Recommendations

1. **Update Case 25SP001154-910:**
   - Current: `property_address = NULL`
   - Set to: `4317 Scaup Court Raleigh, NC, 27616`

2. **Clear Case 25SP000628-310:**
   - Current: `property_address = 5431 Oleander Drive, Lives oNo Wilmington, NC 28403` (attorney)
   - Set to: `NULL`
   - Note: May need to download additional documents (deed of trust) to find actual property

3. **Run Full Re-extraction:**
   ```bash
   PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python extraction/run_extraction.py --overwrite
   ```
   This will:
   - Extract addresses using new patterns
   - Filter out attorney addresses
   - Update database with correct values

4. **Verify Results:**
   ```sql
   -- Check how many cases now have addresses
   SELECT COUNT(*) FROM cases WHERE property_address IS NOT NULL;

   -- Check for attorney addresses that slipped through
   SELECT case_number, property_address
   FROM cases
   WHERE property_address LIKE '%PLLC%'
      OR property_address LIKE '%LLC%'
      OR property_address LIKE '%attorney%';
   ```

---

## Test Execution

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/test_address_extraction.py
```

**Output:** Both test cases passed successfully with expected behavior.
