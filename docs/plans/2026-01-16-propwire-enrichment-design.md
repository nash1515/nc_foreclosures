# PropWire Enrichment Design

## Overview
Add PropWire property links as a QuickLink enrichment for foreclosure cases. PropWire provides property data including valuation, mortgage info, and foreclosure details.

## Problem
PropWire URLs contain unique property IDs that cannot be constructed from address alone:
```
https://propwire.com/realestate/162-Williford-Ln-Spring-Lake-NC-28390/204504433/property-details
                                 ^--- slugified address ---^           ^-- unique ID --^
```

## Solution
Use Playwright to interact with PropWire's autocomplete search, which returns property IDs via their API.

### API Discovery
| Component | Value |
|-----------|-------|
| Endpoint | `POST https://api.propwire.com/api/auto_complete` |
| Request | `{"search": "address", "search_types": ["C","Z","N","T","A"]}` |
| Response | `data[0].id` = property ID, `data[0].address` = normalized address |
| Auth | JWT Bearer token (generated client-side, requires Playwright) |

## Architecture

### File Structure
```
enrichments/prop_wire/
├── __init__.py
├── config.py          # PropWire URLs and constants
├── scraper.py         # Playwright automation for autocomplete search
├── url_builder.py     # Build final PropWire URL from property ID
└── enricher.py        # Main enricher class extending BaseEnricher
```

### File Responsibilities

**config.py**
- BASE_URL = "https://propwire.com"
- PROPERTY_URL_TEMPLATE for building final URLs

**scraper.py**
- `search_by_address(address: str) -> SearchResult`
- Uses Playwright to:
  1. Navigate to propwire.com
  2. Type address in search box
  3. Wait for autocomplete dropdown
  4. Capture property ID from response or click result
- Returns property ID + normalized address (or error)

**url_builder.py**
- `build_property_url(address_slug: str, property_id: str) -> str`
- `slugify_address(address: str) -> str`

**enricher.py**
- `PropWireEnricher(BaseEnricher)`
- `enrich(case_id)` - main entry point
- `_set_enrichment_fields()` - sets propwire_url, propwire_error, propwire_enriched_at

## Database

### Existing Columns (no migration needed)
The enrichments table already has these columns defined:
- `propwire_url` (TEXT) - Final PropWire property URL
- `propwire_enriched_at` (TIMESTAMP) - When enrichment succeeded
- `propwire_error` (TEXT) - Error message if failed

### Error Handling
| Scenario | Action |
|----------|--------|
| 0 matches | Save error: "No property found" |
| 1 match | Save URL + enriched_at |
| 2+ matches | Log to enrichment_review_log for manual review |
| Network error | Save error message, can retry later |

## Integration

### Enrichment Trigger
PropWire enrichment runs automatically when a case moves to `upset_bid` status, alongside existing county RE enrichment.

```python
# enrichments/router.py - enrich_case()
def enrich_case(case_id):
    county_result = run_county_enrichment(case_id)
    propwire_result = PropWireEnricher().enrich(case_id)
    return {'county_re': county_result, 'propwire': propwire_result}
```

### Backfill Script
One-time script to enrich existing upset_bid cases:
```bash
PYTHONPATH=$(pwd) python -m enrichments.prop_wire.backfill
```

### Frontend
Already has PropWire placeholder in dashboard and case detail - will display automatically once propwire_url is populated.

## Implementation Tasks

1. Create `enrichments/prop_wire/config.py` - URLs and constants
2. Create `enrichments/prop_wire/scraper.py` - Playwright search automation
3. Create `enrichments/prop_wire/url_builder.py` - URL construction helpers
4. Create `enrichments/prop_wire/enricher.py` - Main enricher class
5. Create `enrichments/prop_wire/__init__.py` - Module exports
6. Update `enrichments/router.py` - Add PropWire to enrichment flow
7. Create `enrichments/prop_wire/backfill.py` - One-time backfill script
8. Test with single case manually
9. Run backfill on all upset_bid cases
10. Verify QuickLinks display in dashboard

## Performance
- ~3-5 seconds per lookup (Playwright overhead)
- Acceptable for ~39 active upset_bid cases
- Runs asynchronously with case processing
