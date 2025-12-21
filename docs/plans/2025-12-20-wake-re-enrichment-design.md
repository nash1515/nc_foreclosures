# Wake County Real Estate Enrichment - Design Document

**Date:** December 20, 2025
**Author:** Claude (based on brainstorming session)
**Status:** Design Phase
**Related:** nc_foreclosures project

---

## Table of Contents

1. [Overview & Goals](#overview--goals)
2. [Background & Context](#background--context)
3. [Data Flow & Workflow](#data-flow--workflow)
4. [Database Schema](#database-schema)
5. [Module Structure](#module-structure)
6. [Integration Points](#integration-points)
7. [Error Handling & Edge Cases](#error-handling--edge-cases)
8. [Testing Strategy](#testing-strategy)
9. [Implementation Plan](#implementation-plan)
10. [Future Extensibility](#future-extensibility)

---

## Overview & Goals

### Purpose

Create a Wake County Real Estate enrichment module that automatically fetches static property record URLs for foreclosure cases, enabling direct links from the nc_foreclosures dashboard to official county property information.

### Primary Goals

1. **Convert identifiers to URLs:** Transform parcel IDs (preferred) or property addresses (fallback) into Wake County Real Estate account URLs
2. **Persistent storage:** Store enrichment results in a new `enrichments` table for reuse and performance
3. **Dual-trigger system:** Support both event-driven enrichment (on `upset_bid` promotion) and on-demand enrichment (via API/manual requests)
4. **Extensibility:** Design a reusable pattern that other county enrichment modules can follow

### Success Criteria

- ✅ All Wake County `upset_bid` cases have Wake RE URLs within minutes of promotion
- ✅ Zero dashboard latency (URLs pre-fetched, not rendered on-demand)
- ✅ Clear logging and review workflow for ambiguous cases (0 or 2+ matches)
- ✅ Clean separation of concerns for future county modules

### Non-Goals (Out of Scope)

- Scraping dynamic property data (assessed value, tax info, etc.) - only fetching static URLs
- Real-time on-demand lookups during page render
- Historical backfill of existing cases (Phase 1 focuses on new `upset_bid` cases only)

---

## Background & Context

### Current State

- **Parcel IDs discovered:** During Session 18, parcel IDs were found in 1,033+ documents across Wake and Durham counties
- **Wake County format:** 10-digit format (e.g., `0787005323`)
- **Current quicklinks:** Zillow and NC Courts Portal are active; PropWire, Deed, and Property Info are "Coming soon"
- **Dashboard architecture:** Links column with 5 icons, data fetched via API joins

### Wake County RE Portal Structure

**URL patterns:**

1. **PinList lookup (when using parcel ID):**
   ```
   https://services.wake.gov/realestate/PinList.asp?map=0753&sheet=&block=01&lot=8148&spg=
   ```
   - Parcel ID `0753018148` → `map=0753`, `block=01`, `lot=8148`
   - Returns page with Account # link(s)

2. **Address validation (fallback when no parcel ID):**
   ```
   https://services.wake.gov/realestate/ValidateAddress.asp?stnum=414&stname=salem&locidList=&spg=
   ```
   - Parses address into components: street number, prefix, street name, city
   - Returns results table with matching properties

3. **Final account page:**
   ```
   https://services.wake.gov/realestate/Account.asp?id=0379481
   ```
   - The target URL we want to store and link to

### Why This Approach?

- **Static URLs:** Account IDs are persistent and don't require session state
- **Two-step process:** Portal requires intermediate lookup (PinList or ValidateAddress) before revealing account ID
- **Parcel ID preferred:** More reliable than address matching (OCR can mangle addresses)
- **Fallback necessary:** Not all documents contain parcel IDs

---

## Data Flow & Workflow

### Primary Flow: Parcel ID Available

```
┌─────────────────────────────────────────────┐
│ Trigger: Case promoted to upset_bid         │
│          OR manual API request              │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Check: Does case have parcel_id?            │
└────────────────┬────────────────────────────┘
                 │ YES
                 ▼
┌─────────────────────────────────────────────┐
│ Parse parcel ID: 0753018148                 │
│   → map=0753, block=01, lot=8148            │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Construct PinList URL                       │
│ https://services.wake.gov/realestate/       │
│ PinList.asp?map=0753&block=01&lot=8148      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Fetch page, parse HTML table                │
│ Extract Account # (e.g., 0379481)           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Validate results:                           │
│ - 1 match: Success                          │
│ - 0 matches: Log for review                 │
│ - 2+ matches: Log for manual resolution     │
└────────────────┬────────────────────────────┘
                 │ 1 match
                 ▼
┌─────────────────────────────────────────────┐
│ Construct final URL:                        │
│ https://services.wake.gov/realestate/       │
│ Account.asp?id=0379481                      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Save to enrichments table:                  │
│ - wake_re_account: 0379481                  │
│ - wake_re_url: (full URL)                   │
│ - wake_re_enriched_at: NOW()                │
└─────────────────────────────────────────────┘
```

### Fallback Flow: No Parcel ID (Address Search)

```
┌─────────────────────────────────────────────┐
│ Check: Does case have parcel_id?            │
└────────────────┬────────────────────────────┘
                 │ NO
                 ▼
┌─────────────────────────────────────────────┐
│ Parse property_address:                     │
│ "414 S. Salem Street, Apex, NC 27502"       │
│   → stnum=414, prefix=S, name=SALEM,        │
│     type=Street, city=Apex                  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Apply address normalization rules:          │
│ - Strip type designators (St, Rd, Dr, etc.) │
│ - Extract prefix (N, S, E, W)               │
│ - Uppercase street name                     │
│ - Map city to ETJ code (Apex → AP)          │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Construct ValidateAddress URL               │
│ https://services.wake.gov/realestate/       │
│ ValidateAddress.asp?stnum=414&stname=salem  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Fetch results page, parse table rows        │
│ Match criteria:                             │
│ - St Num = 414                              │
│ - Pfx = S (if present in address)           │
│ - Street Name = SALEM                       │
│ - ETJ = AP (city code)                      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ Validate match count:                       │
│ - 1 match: Extract Account #, proceed       │
│ - 0 matches: Log to review queue            │
│ - 2+ matches: Log to review queue           │
└────────────────┬────────────────────────────┘
                 │ 1 match
                 ▼
┌─────────────────────────────────────────────┐
│ Extract Account # from table row            │
│ Construct final URL                         │
│ Save to enrichments table                   │
└─────────────────────────────────────────────┘
```

### Address Parsing Rules

**Street type designators to strip (case-insensitive):**
- Road/Rd/Rd.
- Drive/Dr/Dr.
- Street/St/St.
- Lane/Ln/Ln.
- Avenue/Ave/Ave.
- Boulevard/Blvd/Blvd.
- Court/Ct/Ct.
- Circle/Cir/Cir.
- Way/Wy/Wy.
- Place/Pl/Pl.
- Terrace/Ter/Ter.
- Trail/Trl/Trl.
- Parkway/Pkwy/Pkwy.
- Highway/Hwy/Hwy.

**Directional prefixes to extract (case-insensitive):**
- N, S, E, W
- North, South, East, West

**URL encoding:**
- Use `+` for spaces in street name
- Standard URL encoding for special characters

**ETJ (city) code mapping:**
- Raleigh → RA
- Apex → AP
- Cary → CA
- (Build dynamically from portal reference or hardcode common ones)

---

## Database Schema

### New `enrichments` Table

```sql
CREATE TABLE enrichments (
    id SERIAL PRIMARY KEY,
    case_id INTEGER UNIQUE REFERENCES cases(id) ON DELETE CASCADE,

    -- Wake County RE enrichment
    wake_re_account VARCHAR(20),           -- Account ID (e.g., "0379481")
    wake_re_url TEXT,                      -- Full URL to Account.asp page
    wake_re_enriched_at TIMESTAMP,         -- When enrichment succeeded
    wake_re_error TEXT,                    -- Error message if failed

    -- Future enrichments (placeholders for other counties/sources)
    propwire_url TEXT,
    propwire_enriched_at TIMESTAMP,
    propwire_error TEXT,

    deed_url TEXT,
    deed_enriched_at TIMESTAMP,
    deed_error TEXT,

    property_info_url TEXT,
    property_info_enriched_at TIMESTAMP,
    property_info_error TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_enrichments_case_id ON enrichments(case_id);
```

**Design rationale:**
- **One row per case:** Prevents duplicate enrichment attempts
- **Separate columns per enrichment type:** Allows independent failure states
- **Error tracking:** `wake_re_error` stores failure reasons for debugging
- **Timestamp tracking:** `wake_re_enriched_at` enables age-based refresh logic
- **Extensibility:** New enrichment types add column pairs (url + timestamp + error)

### New Column on `cases` Table

```sql
ALTER TABLE cases ADD COLUMN parcel_id VARCHAR(20);
CREATE INDEX idx_cases_parcel_id ON cases(parcel_id);
```

**Migration notes:**
- Nullable (many cases won't have parcel IDs initially)
- Extracted during OCR processing or AI analysis
- Index for fast lookups during enrichment

### New `enrichment_review_log` Table

```sql
CREATE TABLE enrichment_review_log (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    enrichment_type VARCHAR(50) NOT NULL,  -- 'wake_re', 'propwire', etc.
    search_method VARCHAR(20) NOT NULL,    -- 'parcel_id' or 'address'
    search_value TEXT NOT NULL,            -- The parcel ID or address string used
    matches_found INTEGER NOT NULL,        -- 0 or 2+ (only ambiguous cases logged)
    raw_results JSONB,                     -- Store portal results for debugging
    resolution_notes TEXT,                 -- Admin notes when resolving
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_enrichment_review_case_id ON enrichment_review_log(case_id);
CREATE INDEX idx_enrichment_review_unresolved ON enrichment_review_log(resolved_at) WHERE resolved_at IS NULL;
```

**Purpose:**
- **Ambiguity tracking:** Log cases with 0 or 2+ matches for manual review
- **Debugging:** Store raw HTML results as JSON for investigation
- **Admin workflow:** Admins can review queue and mark items resolved
- **Audit trail:** Track who resolved what and when

---

## Module Structure

```
enrichments/
├── __init__.py
│
├── common/
│   ├── __init__.py
│   ├── base_enricher.py        # Abstract base class with shared logic
│   ├── address_parser.py       # Parse address → components (stnum, prefix, name, city)
│   ├── parcel_extractor.py     # Extract parcel ID from OCR text near keywords
│   └── models.py               # Enrichment, EnrichmentReviewLog SQLAlchemy models
│
└── wake_re/
    ├── __init__.py
    ├── config.py               # Wake-specific constants (ETJ codes, etc.)
    ├── url_builder.py          # URL construction functions
    ├── scraper.py              # Page scraping functions (fetch + parse)
    └── enricher.py             # Main entry point: enrich_case()
```

### Module Responsibilities

#### `enrichments/common/base_enricher.py`

Abstract base class providing shared enrichment logic:

```python
class BaseEnricher(ABC):
    """Abstract base class for all enrichment modules."""

    @abstractmethod
    def enrich(self, case_id: int) -> Dict[str, Any]:
        """
        Enrich a case with external data.

        Returns:
            {
                'success': bool,
                'url': str | None,
                'account_id': str | None,
                'error': str | None,
                'review_needed': bool
            }
        """
        pass

    def _log_review(self, case_id: int, enrichment_type: str,
                    search_method: str, search_value: str,
                    matches_found: int, raw_results: dict):
        """Log cases needing manual review to enrichment_review_log."""
        pass

    def _save_result(self, case_id: int, enrichment_type: str,
                     url: str = None, account_id: str = None,
                     error: str = None):
        """Save enrichment result to enrichments table."""
        pass
```

#### `enrichments/common/address_parser.py`

```python
def parse_address(address: str) -> Dict[str, str]:
    """
    Parse property address into components.

    Args:
        address: "414 S. Salem Street, Apex, NC 27502"

    Returns:
        {
            'stnum': '414',
            'prefix': 'S',
            'name': 'SALEM',
            'type': 'Street',
            'city': 'Apex',
            'state': 'NC',
            'zipcode': '27502'
        }
    """
    pass

def normalize_street_name(name: str) -> str:
    """Strip type designators, uppercase, trim."""
    pass

def extract_prefix(address: str) -> str | None:
    """Extract N/S/E/W prefix if present."""
    pass
```

#### `enrichments/common/parcel_extractor.py`

```python
def extract_parcel_id(text: str, county_code: str) -> str | None:
    """
    Extract parcel ID from OCR text.

    Args:
        text: OCR text from documents
        county_code: '910' (Wake), '180' (Durham), etc.

    Returns:
        Parcel ID string or None

    Strategy:
        - Search for keywords: "Parcel", "PIN", "Property ID", "Tax ID"
        - Find 10-digit numbers nearby (within 100 chars)
        - Validate format (county-specific)
    """
    pass
```

#### `enrichments/wake_re/config.py`

```python
# Wake County Real Estate portal constants

PINLIST_URL_TEMPLATE = (
    "https://services.wake.gov/realestate/PinList.asp"
    "?map={map}&sheet=&block={block}&lot={lot}&spg="
)

VALIDATE_ADDRESS_URL_TEMPLATE = (
    "https://services.wake.gov/realestate/ValidateAddress.asp"
    "?stnum={stnum}&stname={stname}&locidList=&spg="
)

ACCOUNT_URL_TEMPLATE = (
    "https://services.wake.gov/realestate/Account.asp?id={account_id}"
)

# ETJ (city) code mapping
ETJ_CODES = {
    'raleigh': 'RA',
    'apex': 'AP',
    'cary': 'CA',
    'fuquay-varina': 'FV',
    'garner': 'GA',
    'holly springs': 'HS',
    'knightdale': 'KN',
    'morrisville': 'MO',
    'rolesville': 'RO',
    'wake forest': 'WF',
    'wendell': 'WE',
    'zebulon': 'ZE',
}

# Street type designators to strip
STREET_TYPES = [
    'Road', 'Rd', 'Rd.',
    'Drive', 'Dr', 'Dr.',
    'Street', 'St', 'St.',
    'Lane', 'Ln', 'Ln.',
    'Avenue', 'Ave', 'Ave.',
    'Boulevard', 'Blvd', 'Blvd.',
    'Court', 'Ct', 'Ct.',
    'Circle', 'Cir', 'Cir.',
    'Way', 'Wy', 'Wy.',
    'Place', 'Pl', 'Pl.',
    'Terrace', 'Ter', 'Ter.',
    'Trail', 'Trl', 'Trl.',
    'Parkway', 'Pkwy', 'Pkwy.',
    'Highway', 'Hwy', 'Hwy.',
]
```

#### `enrichments/wake_re/url_builder.py`

```python
def parse_parcel_id(parcel_id: str) -> Dict[str, str]:
    """
    Parse 10-digit Wake parcel ID.

    Args:
        parcel_id: "0753018148"

    Returns:
        {'map': '0753', 'block': '01', 'lot': '8148'}
    """
    pass

def build_pinlist_url(parcel_id: str) -> str:
    """Construct PinList URL from parcel ID."""
    pass

def build_validate_address_url(stnum: str, stname: str) -> str:
    """Construct ValidateAddress URL from address components."""
    pass

def build_account_url(account_id: str) -> str:
    """Construct final Account.asp URL."""
    pass
```

#### `enrichments/wake_re/scraper.py`

```python
def fetch_pinlist_results(parcel_id: str) -> List[Dict[str, str]]:
    """
    Fetch and parse PinList results.

    Returns:
        [
            {'account_id': '0379481', 'address': '414 S SALEM ST', ...},
            ...
        ]
    """
    pass

def fetch_validate_address_results(stnum: str, stname: str) -> List[Dict[str, str]]:
    """
    Fetch and parse ValidateAddress results.

    Returns:
        [
            {
                'account_id': '0379481',
                'stnum': '414',
                'prefix': 'S',
                'street_name': 'SALEM',
                'etj': 'AP',
                ...
            },
            ...
        ]
    """
    pass

def match_address_result(results: List[Dict], stnum: str, prefix: str,
                         name: str, etj: str) -> Dict | None:
    """
    Find single matching result from ValidateAddress output.

    Returns:
        Single matching row or None
    """
    pass
```

#### `enrichments/wake_re/enricher.py`

Main entry point:

```python
from enrichments.common.base_enricher import BaseEnricher
from enrichments.wake_re import url_builder, scraper, config

class WakeREEnricher(BaseEnricher):
    def enrich(self, case_id: int) -> Dict[str, Any]:
        """
        Main enrichment workflow for Wake County RE.

        Steps:
            1. Fetch case from DB
            2. Try parcel ID method if available
            3. Fall back to address method if needed
            4. Log ambiguous cases to review queue
            5. Save result to enrichments table

        Returns:
            {
                'success': True/False,
                'url': 'https://...' or None,
                'account_id': '0379481' or None,
                'error': 'Error message' or None,
                'review_needed': True/False
            }
        """
        pass

# Public API
def enrich_case(case_id: int) -> Dict[str, Any]:
    """Convenience function for external calls."""
    enricher = WakeREEnricher()
    return enricher.enrich(case_id)
```

---

## Integration Points

### Trigger 1: Event-Driven (On `upset_bid` Promotion)

**Location:** `extraction/classifier.py`

```python
def _classify_case(case):
    # ... existing classification logic ...

    new_classification = # ... determined classification ...

    if new_classification != case.classification:
        logger.info(f"Case {case.case_number}: {case.classification} → {new_classification}")
        case.classification = new_classification

        # Trigger Wake RE enrichment on upset_bid promotion
        if new_classification == 'upset_bid' and case.county_code == '910':
            try:
                from enrichments.wake_re import enrich_case
                result = enrich_case(case.id)
                if result['success']:
                    logger.info(f"Wake RE enrichment succeeded: {result['url']}")
                elif result['review_needed']:
                    logger.warning(f"Wake RE enrichment needs review: {result['error']}")
                else:
                    logger.error(f"Wake RE enrichment failed: {result['error']}")
            except Exception as e:
                logger.error(f"Wake RE enrichment error: {e}", exc_info=True)
```

**Design notes:**
- Non-blocking: Enrichment errors don't prevent classification
- County-specific: Only runs for Wake County (`county_code == '910'`)
- Logged results: All outcomes logged for debugging

### Trigger 2: On-Demand API Endpoint

**Location:** `web_app/api/enrichments.py` (new file)

```python
from flask import Blueprint, jsonify, request
from web_app.auth.middleware import require_auth
from enrichments.wake_re import enrich_case as enrich_wake_re

bp = Blueprint('enrichments', __name__)

@bp.route('/api/enrichments/wake-re/<int:case_id>', methods=['POST'])
@require_auth
def trigger_wake_re_enrichment(case_id):
    """
    Manually trigger Wake RE enrichment for a case.

    Use cases:
        - Retry failed enrichments
        - Enrich historical cases
        - Admin-initiated bulk enrichment
    """
    try:
        result = enrich_wake_re(case_id)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/enrichments/review-queue', methods=['GET'])
@require_auth
def get_review_queue():
    """
    Fetch unresolved enrichment review items.

    Returns:
        [
            {
                'id': 1,
                'case_number': '25SP000050-910',
                'enrichment_type': 'wake_re',
                'search_method': 'address',
                'search_value': '414 S Salem St, Apex, NC',
                'matches_found': 2,
                'raw_results': [...],
                'created_at': '...'
            },
            ...
        ]
    """
    pass

@bp.route('/api/enrichments/resolve/<int:log_id>', methods=['POST'])
@require_auth
def resolve_review_item(log_id):
    """
    Mark enrichment review item as resolved.

    Body:
        {
            'account_id': '0379481',  # Selected account (if manual resolution)
            'notes': 'Admin notes...'
        }
    """
    pass
```

**Register blueprint in `web_app/app.py`:**

```python
from web_app.api import enrichments
app.register_blueprint(enrichments.bp)
```

### Dashboard Integration

**API changes in `web_app/api/cases.py`:**

```python
@bp.route('/api/cases/upset-bids', methods=['GET'])
def get_upset_bids():
    # ... existing query ...

    # Add join with enrichments table
    query = db.session.query(
        Case,
        Enrichment.wake_re_url
    ).outerjoin(
        Enrichment, Case.id == Enrichment.case_id
    ).filter(
        Case.classification == 'upset_bid'
    )

    results = []
    for case, wake_re_url in query:
        results.append({
            # ... existing fields ...
            'wake_re_url': wake_re_url,
        })

    return jsonify(results)
```

**Frontend changes in `frontend/src/pages/Dashboard.jsx`:**

```jsx
const columns = [
    // ... existing columns ...
    {
        title: 'Links',
        key: 'links',
        render: (_, record) => (
            <Space size="small">
                <Tooltip title="NC Courts Portal">
                    <a href={ncCourtsUrl(record)} target="_blank">
                        <GavelIcon />
                    </a>
                </Tooltip>
                <Tooltip title="Zillow">
                    <a href={zillowUrl(record)} target="_blank">
                        <ZillowIcon />
                    </a>
                </Tooltip>
                <Tooltip title={record.wake_re_url ? "Wake County Property Info" : "Coming soon"}>
                    <a
                        href={record.wake_re_url || '#'}
                        target="_blank"
                        style={{ opacity: record.wake_re_url ? 1 : 0.3 }}
                        onClick={(e) => !record.wake_re_url && e.preventDefault()}
                    >
                        <PropertyInfoIcon />
                    </a>
                </Tooltip>
                {/* PropWire, Deed icons ... */}
            </Space>
        ),
    },
];
```

### Parcel ID Extraction Integration

**Option 1: OCR-based extraction in `extraction/extractor.py`**

```python
def _extract_parcel_id(text: str, county_code: str) -> str | None:
    """Extract parcel ID from OCR text."""
    if county_code == '910':  # Wake County
        # Pattern: 10-digit number near keywords
        pattern = r'(?:Parcel|PIN|Property\s+ID|Tax\s+ID)[:\s]*(\d{10})'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def update_case_with_extracted_data(case_id, documents):
    # ... existing extraction logic ...

    # Extract parcel ID if not already set
    if not case.parcel_id:
        for doc in documents:
            if doc.ocr_text:
                parcel_id = _extract_parcel_id(doc.ocr_text, case.county_code)
                if parcel_id:
                    case.parcel_id = parcel_id
                    logger.info(f"Extracted parcel ID {parcel_id} from {doc.title}")
                    break
```

**Option 2: AI-based extraction in `analysis/prompt_builder.py`**

Add to AI analysis prompt:

```python
Please extract the following if present:
- Parcel ID / PIN / Property ID (usually 10 digits for Wake County)
```

Parse from AI response in `analysis/analyzer.py`:

```python
if 'parcel_id' in analysis_result:
    case.parcel_id = analysis_result['parcel_id']
```

**Recommendation:** Use both methods:
1. OCR extraction runs first (faster, cheaper)
2. AI extraction as backup (more context-aware)

---

## Error Handling & Edge Cases

### Scraping Errors

| Error Type | Handling Strategy | Recovery |
|------------|------------------|----------|
| Network timeout | Retry once with 30s timeout | Save error to `wake_re_error` |
| HTTP 404/500 | Log error, don't retry | Save error message |
| Portal structure changed | Log error for investigation | Alert admin via review queue |
| Account # not found in HTML | Log as error | Mark for manual review |

**Implementation:**

```python
def _fetch_with_retry(url: str, max_retries: int = 1) -> str:
    """Fetch URL with retry logic."""
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            if attempt == max_retries:
                raise
            logger.warning(f"Fetch attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
```

### Address Search Edge Cases

| Scenario | Example | Handling |
|----------|---------|----------|
| 0 matches | Invalid address or outside Wake County | Log to review queue with search params |
| 2+ matches | "100 Main St" exists in multiple cities | Log to review queue with all matches |
| ETJ code unknown | New city not in mapping | Try without ETJ filter, log warning |
| Address missing city | "414 Salem St" | Extract from full case data, or fail |
| OCR mangled address | "4l4 S Sa1em St" | Attempt correction (l→1, 1→I), or fail |

**Multiple matches handling:**

```python
def _handle_multiple_matches(case_id, results, search_value):
    """Log cases with 2+ matches to review queue."""
    from enrichments.common.models import EnrichmentReviewLog

    log = EnrichmentReviewLog(
        case_id=case_id,
        enrichment_type='wake_re',
        search_method='address',
        search_value=search_value,
        matches_found=len(results),
        raw_results={'results': results}  # Store as JSONB
    )
    db.session.add(log)
    db.session.commit()

    logger.warning(f"Case {case_id}: {len(results)} matches for '{search_value}'")
```

### Parcel ID Edge Cases

| Scenario | Example | Handling |
|----------|---------|----------|
| Not 10 digits | "075301" (truncated) | Fall back to address search |
| Invalid format | Contains letters | Fall back to address search |
| Multiple in OCR | Two parcel IDs in same doc | Take first near keyword, log warning |
| Parcel not in portal | New development? | Log to review queue |

**Validation:**

```python
def _validate_parcel_id(parcel_id: str) -> bool:
    """Validate Wake County parcel ID format."""
    if not parcel_id:
        return False
    if len(parcel_id) != 10:
        return False
    if not parcel_id.isdigit():
        return False
    return True
```

### Database Constraints & Race Conditions

**Unique constraint on `enrichments.case_id`:**
- Prevents duplicate enrichment rows
- `ON CONFLICT DO UPDATE` for idempotent retries:

```python
def _save_result(case_id, url, account_id, error):
    """Save enrichment result with upsert logic."""
    from enrichments.common.models import Enrichment

    enrichment = db.session.query(Enrichment).filter_by(case_id=case_id).first()
    if not enrichment:
        enrichment = Enrichment(case_id=case_id)
        db.session.add(enrichment)

    enrichment.wake_re_url = url
    enrichment.wake_re_account = account_id
    enrichment.wake_re_error = error
    enrichment.wake_re_enriched_at = datetime.now() if url else None
    enrichment.updated_at = datetime.now()

    db.session.commit()
```

### Logging Strategy

**Log levels:**
- `DEBUG`: URL construction, parsing steps
- `INFO`: Successful enrichment, account # extracted
- `WARNING`: Ambiguous results (0 or 2+ matches), OCR issues
- `ERROR`: Network failures, parsing errors, unexpected exceptions

**Log format:**

```python
logger.info(f"Case {case.case_number}: Wake RE enrichment succeeded - {url}")
logger.warning(f"Case {case.case_number}: {matches} matches for parcel {parcel_id}")
logger.error(f"Case {case.case_number}: Failed to fetch {url} - {error}")
```

---

## Testing Strategy

### Unit Tests

**`tests/enrichments/test_address_parser.py`:**

```python
def test_parse_address_full():
    result = parse_address("414 S. Salem Street, Apex, NC 27502")
    assert result['stnum'] == '414'
    assert result['prefix'] == 'S'
    assert result['name'] == 'SALEM'
    assert result['type'] == 'Street'
    assert result['city'] == 'Apex'

def test_normalize_street_name():
    assert normalize_street_name("Salem Street") == "SALEM"
    assert normalize_street_name("Main Rd.") == "MAIN"
    assert normalize_street_name("Oak Dr") == "OAK"
```

**`tests/enrichments/test_url_builder.py`:**

```python
def test_parse_parcel_id():
    result = parse_parcel_id("0753018148")
    assert result == {'map': '0753', 'block': '01', 'lot': '8148'}

def test_build_pinlist_url():
    url = build_pinlist_url("0753018148")
    assert "map=0753" in url
    assert "block=01" in url
    assert "lot=8148" in url
```

**`tests/enrichments/test_scraper.py`:**

```python
def test_parse_pinlist_results():
    html = """
    <table>
        <tr><td><a href="Account.asp?id=0379481">0379481</a></td></tr>
    </table>
    """
    results = _parse_pinlist_html(html)
    assert len(results) == 1
    assert results[0]['account_id'] == '0379481'
```

### Integration Tests

**`tests/enrichments/test_wake_re_integration.py`:**

```python
@mock.patch('enrichments.wake_re.scraper.requests.get')
def test_enrich_case_with_parcel_id(mock_get):
    # Setup: Create test case with parcel ID
    case = Case(case_number='TEST-001', county_code='910', parcel_id='0753018148')
    db.session.add(case)
    db.session.commit()

    # Mock HTTP responses
    mock_get.return_value.text = """<a href="Account.asp?id=0379481">0379481</a>"""

    # Execute
    result = enrich_case(case.id)

    # Verify
    assert result['success'] == True
    assert '0379481' in result['url']

    enrichment = Enrichment.query.filter_by(case_id=case.id).first()
    assert enrichment.wake_re_account == '0379481'

@mock.patch('enrichments.wake_re.scraper.requests.get')
def test_enrich_case_address_fallback(mock_get):
    # Setup: Case without parcel ID
    case = Case(
        case_number='TEST-002',
        county_code='910',
        property_address='414 S Salem St, Apex, NC 27502'
    )
    db.session.add(case)
    db.session.commit()

    # Mock ValidateAddress response
    mock_get.return_value.text = """
    <tr>
        <td>414</td><td>S</td><td>SALEM</td><td>AP</td>
        <td><a href="Account.asp?id=0379481">0379481</a></td>
    </tr>
    """

    # Execute
    result = enrich_case(case.id)

    # Verify
    assert result['success'] == True
    assert result['url'] is not None
```

### Live Validation Tests

**Manual testing checklist:**

1. **Parcel ID happy path:**
   - [ ] Case with valid 10-digit parcel ID
   - [ ] PinList returns single account
   - [ ] Final URL opens correct property page

2. **Address fallback:**
   - [ ] Case without parcel ID
   - [ ] ValidateAddress returns single match
   - [ ] Final URL opens correct property page

3. **Edge cases:**
   - [ ] Case with invalid parcel ID (falls back to address)
   - [ ] Case with ambiguous address (logs to review queue)
   - [ ] Case with no matches (logs to review queue)
   - [ ] Network failure (retries then logs error)

4. **Real Wake County cases:**
   - Test with 5-10 actual `upset_bid` cases from production DB
   - Manually verify URLs resolve correctly
   - Check for false positives (wrong properties)

**Test data sources:**
- Use existing Wake County cases from `cases` table
- Filter for `upset_bid` and `closed_sold` classifications
- Ensure mix of parcel ID presence/absence

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

**Tasks:**
1. ✅ Create database migrations
   - `migrations/add_parcel_id_column.sql`
   - `migrations/create_enrichments_table.sql`
   - `migrations/create_enrichment_review_log.sql`

2. ✅ Implement common utilities
   - `enrichments/common/models.py` (SQLAlchemy models)
   - `enrichments/common/base_enricher.py` (abstract base class)
   - `enrichments/common/address_parser.py`
   - `enrichments/common/parcel_extractor.py`

3. ✅ Unit tests for common utilities
   - Test address parsing edge cases
   - Test parcel ID validation
   - Test ETJ code mapping

**Deliverable:** Common enrichment framework ready for Wake RE module

### Phase 2: Wake RE Module (Week 1-2)

**Tasks:**
1. ✅ Implement Wake RE module
   - `enrichments/wake_re/config.py`
   - `enrichments/wake_re/url_builder.py`
   - `enrichments/wake_re/scraper.py`
   - `enrichments/wake_re/enricher.py`

2. ✅ Integration tests
   - Mock HTTP responses
   - Test parcel ID flow
   - Test address fallback flow
   - Test error cases

3. ✅ Live validation
   - Test with 5-10 real cases
   - Verify URL accuracy
   - Document any portal quirks

**Deliverable:** Functional Wake RE enrichment module

### Phase 3: Integration & API (Week 2)

**Tasks:**
1. ✅ Add parcel ID extraction
   - Update `extraction/extractor.py` (OCR-based)
   - Update `analysis/prompt_builder.py` (AI-based)
   - Backfill existing `upset_bid` cases

2. ✅ Add enrichment triggers
   - Classifier integration (`extraction/classifier.py`)
   - API endpoints (`web_app/api/enrichments.py`)
   - Scheduler integration (optional: bulk enrichment cron)

3. ✅ Frontend integration
   - Update API to include `wake_re_url`
   - Add Property Info icon to Dashboard
   - Add enrichment status to Case Detail

**Deliverable:** End-to-end enrichment pipeline operational

### Phase 4: Admin Tools & Monitoring (Week 2-3)

**Tasks:**
1. ✅ Review queue UI
   - Admin tab section for enrichment review
   - Display cases with 0 or 2+ matches
   - Resolve button to manually select account

2. ✅ Bulk enrichment tools
   - Admin endpoint: `POST /api/admin/enrich-all-wake`
   - Script: `scripts/backfill_wake_enrichments.py`

3. ✅ Monitoring & alerts
   - Daily enrichment success rate
   - Review queue size alerts
   - Error trend analysis

**Deliverable:** Production-ready admin tools

### Phase 5: Documentation & Handoff (Week 3)

**Tasks:**
1. ✅ Developer documentation
   - Module architecture guide
   - Adding new enrichment types (Durham, Harnett, etc.)
   - Troubleshooting guide

2. ✅ User documentation
   - Property Info quicklink usage
   - Review queue workflow
   - Manual enrichment triggers

3. ✅ Code review & cleanup
   - Remove debug logging
   - Add type hints
   - Docstring coverage

**Deliverable:** Fully documented and ready for production

---

## Future Extensibility

### Adding New Enrichment Types

**Example: Durham County RE**

1. Create module: `enrichments/durham_re/`
   - Extend `BaseEnricher`
   - Implement Durham-specific scraping logic
   - Add columns to `enrichments` table: `durham_re_url`, `durham_re_enriched_at`, `durham_re_error`

2. Update triggers:
   - Add `county_code == '180'` check in classifier
   - Add API endpoint: `/api/enrichments/durham-re/<case_id>`

3. Frontend integration:
   - Add Durham icon/logic to quicklinks

**Example: PropWire enrichment**

1. Create module: `enrichments/propwire/`
   - API-based (not scraping)
   - Implement rate limiting
   - Add columns: `propwire_url`, `propwire_enriched_at`, `propwire_error`

2. Trigger: On `upset_bid` promotion (all counties)

3. Frontend: Activate PropWire icon in Links column

### Extensibility Design Principles

1. **Column pairs:** Every enrichment type uses 3 columns (url, timestamp, error)
2. **County-agnostic base class:** Shared logic in `BaseEnricher`
3. **Modular structure:** Each enrichment type in separate directory
4. **Unified review queue:** All enrichments log to same `enrichment_review_log` table
5. **API pattern:** All enrichments follow `/api/enrichments/<type>/<case_id>` pattern

### Configuration-Driven Enrichment

**Future enhancement: `enrichments/config.yaml`**

```yaml
enrichments:
  - type: wake_re
    enabled: true
    triggers:
      - event: classification_change
        conditions:
          - classification: upset_bid
          - county_code: 910
    priority: 1

  - type: durham_re
    enabled: true
    triggers:
      - event: classification_change
        conditions:
          - classification: upset_bid
          - county_code: 180
    priority: 2

  - type: propwire
    enabled: false
    triggers:
      - event: classification_change
        conditions:
          - classification: upset_bid
    rate_limit: 100/day
    priority: 3
```

This would enable dynamic enrichment routing without code changes.

---

## Appendix

### Wake County Portal Reference

**Portal URLs:**
- Home: https://services.wake.gov/realestate/
- PinList: https://services.wake.gov/realestate/PinList.asp
- ValidateAddress: https://services.wake.gov/realestate/ValidateAddress.asp
- Account: https://services.wake.gov/realestate/Account.asp

**HTML structure notes:**
- Results are in `<table>` tags
- Account links: `<a href="Account.asp?id=XXXXXXX">XXXXXXX</a>`
- ETJ codes in results table (column varies)

### County Code Reference

| County | Code | Parcel Format | Status |
|--------|------|---------------|--------|
| Wake | 910 | 10-digit (0753018148) | In scope |
| Durham | 180 | 10-digit (0831912409) | Future |
| Harnett | 390 | Unknown | Future |
| Lee | 540 | Unknown | Future |
| Orange | 680 | Unknown | Future |
| Chatham | 150 | Unknown | Future |

### Related Documents

- `CLAUDE.md` - Project overview and session history
- `docs/SESSION_HISTORY.md` - Detailed session logs
- `extraction/README.md` - Extraction pipeline documentation

### Questions for User

1. **Backfill priority:** Should we enrich all existing `upset_bid` cases immediately, or only new cases going forward?
2. **Review queue workflow:** Who will handle manual resolution of ambiguous cases? Need admin training?
3. **Performance:** Should enrichment run synchronously (blocking) or asynchronously (background task)?
4. **Error notifications:** Email alerts for high review queue volume, or just dashboard warnings?
5. **Parcel ID extraction:** Prefer OCR-only, AI-only, or hybrid approach?

---

**End of Design Document**
