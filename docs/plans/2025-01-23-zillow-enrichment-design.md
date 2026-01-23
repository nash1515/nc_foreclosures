# Zillow Enrichment Integration Design

**Date:** 2025-01-23
**Status:** Draft

## Overview

Integrate the external `zillow_scraper` project to automatically fetch Zillow URLs and Zestimates for foreclosure cases. Enrichment runs when cases are classified as `upset_bid`, providing real-time property valuations to support investment decisions.

## Goals

1. Automatically enrich `upset_bid` cases with Zillow data
2. Provide Zillow URLs and Zestimates in Case Detail view
3. Display Zestimates in Dashboard for quick comparison
4. Support manual re-enrichment via API
5. Handle rate limiting and error conditions gracefully

## Database Schema

### Changes to `enrichments` Table

Add the following columns:

```sql
ALTER TABLE enrichments ADD COLUMN zillow_url TEXT;
ALTER TABLE enrichments ADD COLUMN zillow_zestimate INTEGER; -- in dollars
ALTER TABLE enrichments ADD COLUMN zillow_enriched_at TIMESTAMP;
ALTER TABLE enrichments ADD COLUMN zillow_error TEXT;
```

**Notes:**
- `zillow_zestimate` stores the value in dollars (e.g., 350000 for $350,000)
- `zillow_error` stores error messages from failed lookups
- `zillow_enriched_at` tracks when enrichment occurred

## Installation

The `zillow_scraper` project is located at `/home/ahn/projects/zillow_scraper`.

Install as an editable package in the `nc_foreclosures` virtual environment:

```bash
source venv/bin/activate
pip install -e /home/ahn/projects/zillow_scraper
```

This allows importing with:
```python
from zillow_scraper import lookup
```

## Implementation

### 1. Enricher Class

**File:** `enrichments/zillow/enricher.py`

Follow the `BaseEnricher` pattern used by other enrichers:

```python
from enrichments.base import BaseEnricher
from zillow_scraper import lookup
import time

class ZillowEnricher(BaseEnricher):
    enrichment_type = 'zillow'

    def enrich(self, case_id: int, force: bool = False) -> dict:
        """
        Enrich case with Zillow data.

        Args:
            case_id: Case ID to enrich
            force: If True, re-enrich even if already enriched

        Returns:
            dict with keys: success, zillow_url, zillow_zestimate, error
        """
        # Get case and check if property_address exists
        # Skip if already enriched (unless force=True)
        # Call zillow_scraper.lookup(address)
        # Save results to enrichments table
        # Return result dict
```

**Key behaviors:**
- Skip if `property_address` is None or empty
- Skip if already enriched (check `zillow_enriched_at`) unless `force=True`
- Log warnings for missing addresses
- Store both successful and failed lookups
- Return structured dict with `success`, `zillow_url`, `zillow_zestimate`, `error` keys

### 2. Router Integration

**File:** `enrichments/router.py`

Add Zillow enrichment after PropWire in the enrichment chain:

```python
from enrichments.zillow.enricher import ZillowEnricher

def enrich_case(case_id: int, force: bool = False):
    """Run all enrichments for a case."""
    results = {}

    # Existing enrichments (RE data, deed URLs, PropWire)
    # ...

    # Zillow enrichment with rate limiting
    time.sleep(5)  # 5-second delay before Zillow lookup
    zillow_enricher = ZillowEnricher()
    results['zillow'] = zillow_enricher.enrich(case_id, force=force)

    return results
```

**Rate limiting:** 5-second delay before each Zillow lookup to avoid triggering anti-bot measures.

### 3. API Endpoints

#### GET /api/cases/<case_id>

**Changes:**
- Include `zillow_url` and `zillow_zestimate` in response
- Nested under enrichments object

**Example response:**
```json
{
  "id": 123,
  "case_number": "24 CVD 1234",
  "enrichments": {
    "property_address": "123 Main St",
    "zillow_url": "https://www.zillow.com/homedetails/...",
    "zillow_zestimate": 350000
  }
}
```

#### GET /api/cases (list)

**Changes:**
- Include `zillow_zestimate` for each case
- Used to display Zestimate column in Dashboard

#### POST /api/enrichments/zillow/<case_id>

**New endpoint for manual enrichment:**

```python
@enrichments_bp.route('/zillow/<int:case_id>', methods=['POST'])
def enrich_zillow(case_id):
    """Manually trigger Zillow enrichment for a case."""
    force = request.args.get('force', 'false').lower() == 'true'

    enricher = ZillowEnricher()
    result = enricher.enrich(case_id, force=force)

    return jsonify(result), 200 if result['success'] else 500
```

**Usage:**
- `POST /api/enrichments/zillow/123` - Enrich case 123 (skip if already enriched)
- `POST /api/enrichments/zillow/123?force=true` - Force re-enrichment

## Frontend Changes

### Case Detail View

#### Quick Links Section

**Current behavior:** Client-side URL construction using property_address

**New behavior:**
1. If `zillow_url` exists in enrichments, use it directly
2. Otherwise, fall back to client-side URL construction
3. Show Zestimate in tooltip when hovering over Zillow link

**Implementation:**
```javascript
const zillowUrl = caseData.enrichments?.zillow_url || constructZillowUrl(address);
const zestimate = caseData.enrichments?.zillow_zestimate;

<a href={zillowUrl} target="_blank" rel="noopener noreferrer">
  <Tooltip title={zestimate ? `Zestimate: $${zestimate.toLocaleString()}` : 'View on Zillow'}>
    Zillow
  </Tooltip>
</a>
```

### Dashboard View

#### New Column: Zestimate

Add a new column to the case list table:

**Column configuration:**
- Title: "Zestimate"
- Position: After "County" or "Status" column
- Format: Currency with comma separators (e.g., "$350,000")
- Sort: Numeric descending
- Filter: None (can add range filter later)

**Implementation:**
```javascript
{
  title: 'Zestimate',
  dataIndex: ['enrichments', 'zillow_zestimate'],
  key: 'zestimate',
  sorter: (a, b) => (a.enrichments?.zillow_zestimate || 0) - (b.enrichments?.zillow_zestimate || 0),
  render: (zestimate) => zestimate ? `$${zestimate.toLocaleString()}` : '-',
}
```

## Edge Cases

### 1. Missing Property Address

**Scenario:** Case has no `property_address`

**Behavior:**
- Skip enrichment
- Log warning: `"Skipping Zillow enrichment for case {case_id}: no property_address"`
- Do not create enrichment record

### 2. Not Found Error

**Scenario:** `zillow_scraper.lookup()` returns `{'error': 'not_found'}`

**Behavior:**
- Store error in `zillow_error` column
- Set `zillow_enriched_at` to current timestamp
- Do not auto-retry (requires manual intervention or force re-enrichment)
- Frontend displays "-" for Zestimate

### 3. Blocked Error

**Scenario:** `zillow_scraper.lookup()` returns `{'error': 'blocked'}`

**Behavior:**
- Store error in `zillow_error` column
- Set `zillow_enriched_at` to current timestamp
- Log error for manual attention
- Admin can manually trigger re-enrichment later

### 4. Zestimate is Null

**Scenario:** Zillow URL found but no Zestimate available

**Behavior:**
- Store `zillow_url` anyway (still valuable for manual review)
- Set `zillow_zestimate` to NULL
- Frontend displays "-" but link still works

### 5. Re-enrichment

**Scenario:** Enrichment already exists for a case

**Default behavior (`force=False`):**
- Skip enrichment
- Return existing data
- Log: `"Zillow enrichment already exists for case {case_id}"`

**Force behavior (`force=True`):**
- Re-run enrichment
- Update existing record with new data
- Update `zillow_enriched_at` timestamp

## Testing Checklist

- [ ] Database migration runs successfully
- [ ] `zillow_scraper` imports correctly in nc_foreclosures venv
- [ ] Enricher creates enrichment records for valid addresses
- [ ] Enricher skips cases without property_address
- [ ] Enricher handles `not_found` errors gracefully
- [ ] Enricher handles `blocked` errors gracefully
- [ ] Enricher skips already-enriched cases (unless force=True)
- [ ] Router integration includes 5-second delay
- [ ] API returns zillow_url and zillow_zestimate in case detail
- [ ] API returns zillow_zestimate in case list
- [ ] Manual enrichment endpoint works with and without force parameter
- [ ] Frontend displays Zestimate in tooltip on Case Detail
- [ ] Frontend displays Zestimate column in Dashboard
- [ ] Frontend handles missing Zestimate gracefully (displays "-")

## Deployment Notes

1. Run database migration to add new columns
2. Install `zillow_scraper` in production venv: `pip install -e /home/ahn/projects/zillow_scraper`
3. Restart Flask API and scheduler
4. Monitor logs for Zillow enrichment errors
5. Manually trigger enrichment for existing `upset_bid` cases: `POST /api/enrichments/zillow/<case_id>?force=true`

## Future Enhancements

1. **Retry logic for blocked errors** - Exponential backoff with configurable retry limits
2. **Zestimate history tracking** - Store historical Zestimates to track value changes
3. **Dashboard filters** - Add Zestimate range filter (e.g., "$200k-$400k")
4. **Rent Zestimate** - Fetch rental estimates for investment analysis
5. **Property photos** - Store primary photo URL from Zillow
6. **Days on Zillow** - Track listing duration if property is for sale

## References

- Zillow scraper project: `/home/ahn/projects/zillow_scraper`
- Existing enrichers: `enrichments/propwire/`, `enrichments/deed_urls/`
- Base enricher pattern: `enrichments/base.py`
- Router: `enrichments/router.py`
