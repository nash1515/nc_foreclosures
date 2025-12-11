# Address Extraction Fix

**Date:** 2025-12-09
**File:** `/home/ahn/projects/nc_foreclosures/extraction/extractor.py`

## Problem

The address extraction patterns were too generic and matched the FIRST address found in documents, which was often an attorney or defendant address rather than the property being foreclosed.

### Example Issues

- **Case 25SP001147-910**: Database had "813 Clarence Jordan Ct, Wendell, NC 27591" (an heir's address from the "TO:" section) instead of the correct property address "2420 Rogers Circle, Wake Forest, NC 27587"
- Generic patterns matched addresses in defendant/heir listings before finding properly-labeled property addresses

## Solution

### 1. Reordered Patterns by Priority

Changed `ADDRESS_PATTERNS` from simple regex strings to tuples of `(regex, label)` and reordered them:

**HIGHEST PRIORITY** - Explicit property labels:
- "The address for the real property is:"
- "Property Address (to post):"
- "real property located at"
- "property secured by"

**HIGH PRIORITY** - Standard foreclosure headers:
- "ADDRESS/LOCATION OF PROPERTY BEING FORECLOSED"
- "Address of property:"

**MEDIUM PRIORITY** - Common patterns:
- "commonly known as"
- "Property Address:"

**LOWEST PRIORITY** - Generic fallback:
- Generic street address pattern (only used when no explicit labels found)

### 2. Added Rejection Contexts

Created `REJECT_ADDRESS_CONTEXTS` list to filter out wrong addresses:

```python
REJECT_ADDRESS_CONTEXTS = [
    r'Name\s+And\s+Address\s+Of\s+(?:Attorney|Agent)',
    r'Attorney\s+Or\s+Agent\s+For\s+Upset\s+Bidder',
    r'Heir\s+of\s+',
    r'TO:\s*\n',
    r'Current\s+Resident',
    r'DEFENDANT[:\s]',
    r'defendant[:\s]',
    r'Unknown\s+Heirs',
    r'Unknown\s+Spouse',
    r'or\s+to\s+the\s+heirs',
    r'service\s+of\s+process',
    r'last\s+known\s+address',
]
```

### 3. Enhanced Context Checking

Updated `extract_property_address()` to:
- Check 300 characters BEFORE each match (expanded from 200)
- Check for rejection contexts FIRST, before attorney indicators
- Check for form artifacts
- Log which pattern matched (for debugging)
- Skip rejected matches and try next pattern

## Results

### Test Case Results

**Case 24SP002363-910:**
- Database: "109 Tupelo Grove Lane, Holly Springs, NC 27540"
- Extracted: "109 Tupelo Grove Lane, Holly Springs, NC 27540"
- **Status:** ✓ MATCH (correct)

**Case 25SP001147-910:**
- Database: "813 Clarence Jordan Ct, Wendell, NC 27591" (WRONG - heir address)
- Extracted: "2420 Rogers Circle, Wake Forest, NC 27587" (CORRECT - from "The address for the real property is:")
- **Status:** ✓ CORRECT (extraction fixed the database error)

## Implementation Details

### Pattern Structure

Old:
```python
ADDRESS_PATTERNS = [
    r'ADDRESS/LOCATION\s+OF\s+PROPERTY...',  # Just regex
    ...
]
```

New:
```python
ADDRESS_PATTERNS = [
    (r'The\s+address\s+for\s+the\s+real\s+property\s+is[:\s]*\n?\s*...', 'real_property'),  # Tuple
    ...
]
```

### Extraction Flow

1. Try each pattern in priority order
2. For each match:
   - Extract context (300 chars before match)
   - Check rejection contexts → REJECT if found
   - Check attorney indicators → REJECT if found
   - Check form artifacts → REJECT if found
   - ACCEPT and return address
3. If all patterns tried and no match, return None

## Key Improvements

1. **Explicit labels prioritized** - Addresses with clear property labels (e.g., "The address for the real property is:") are found first
2. **Defendant/heir addresses rejected** - Addresses in "TO:" sections with "Heir of" or "Current Resident" are skipped
3. **Attorney addresses rejected** - Addresses near law firm names or "Attorney Or Agent" are skipped
4. **Pattern order matters** - Generic patterns only used as fallback when no explicit labels found

## Future Considerations

- May need to add more rejection contexts as new edge cases are discovered
- Could add validation to compare extracted addresses with county property records
- Consider flagging cases where extracted address differs from database for manual review
