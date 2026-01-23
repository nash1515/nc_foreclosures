# Zillow Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate zillow_scraper to fetch and store Zillow URLs and Zestimates for upset_bid cases.

**Architecture:** New ZillowEnricher following BaseEnricher pattern, called from router after PropWire. Stores zillow_url and zillow_zestimate in enrichments table. Frontend displays zestimate on dashboard and uses stored URL for links.

**Tech Stack:** Python, SQLAlchemy, Flask API, React/Ant Design frontend, external zillow_scraper package

---

## Task 0: Install zillow_scraper Package

**Step 1: Install editable package**

```bash
cd /home/ahn/projects/nc_foreclosures
source venv/bin/activate
pip install -e /home/ahn/projects/zillow_scraper
```

**Step 2: Verify installation**

```bash
python -c "from zillow_scraper import lookup, ZillowResult, ZillowError; print('OK')"
```
Expected: `OK`

**Step 3: Commit requirements update**

```bash
pip freeze | grep -i zillow
# Should show: zillow-scraper @ file:///home/ahn/projects/zillow_scraper
```

No commit needed (editable install doesn't go in requirements.txt)

---

## Task 1: Database Migration

**Files:**
- Create: `database/migrations/add_zillow_columns.sql`

**Step 1: Write migration SQL**

Create `database/migrations/add_zillow_columns.sql`:

```sql
-- Add Zillow enrichment columns to enrichments table
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_url TEXT;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_zestimate INTEGER;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_enriched_at TIMESTAMP;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_error TEXT;
```

**Step 2: Run migration**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f database/migrations/add_zillow_columns.sql
```

Expected: `ALTER TABLE` (4 times)

**Step 3: Verify columns exist**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d enrichments" | grep zillow
```

Expected output shows 4 zillow columns

**Step 4: Commit**

```bash
git add database/migrations/add_zillow_columns.sql
git commit -m "feat: add zillow columns to enrichments table"
```

---

## Task 2: Update SQLAlchemy Model

**Files:**
- Modify: `enrichments/common/models.py`

**Step 1: Add Zillow columns to Enrichment model**

In `enrichments/common/models.py`, add after the `property_info_error` column (around line 67):

```python
    # Zillow enrichment
    zillow_url = Column(Text)
    zillow_zestimate = Column(Integer)
    zillow_enriched_at = Column(TIMESTAMP)
    zillow_error = Column(Text)
```

**Step 2: Verify model loads**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from enrichments.common.models import Enrichment; print([c.name for c in Enrichment.__table__.columns if 'zillow' in c.name])"
```

Expected: `['zillow_url', 'zillow_zestimate', 'zillow_enriched_at', 'zillow_error']`

**Step 3: Commit**

```bash
git add enrichments/common/models.py
git commit -m "feat: add zillow columns to Enrichment model"
```

---

## Task 3: Create Zillow Enricher

**Files:**
- Create: `enrichments/zillow/__init__.py`
- Create: `enrichments/zillow/enricher.py`

**Step 1: Create directory and __init__.py**

Create `enrichments/zillow/__init__.py`:

```python
"""Zillow enrichment module."""
from .enricher import enrich_case, ZillowEnricher

__all__ = ['enrich_case', 'ZillowEnricher']
```

**Step 2: Create enricher**

Create `enrichments/zillow/enricher.py`:

```python
"""Zillow enrichment using external zillow_scraper package."""
import logging
import time
from datetime import datetime
from typing import Optional

from zillow_scraper import lookup, ZillowResult, ZillowError

from common.database import get_session
from common.models import Case
from enrichments.common.base_enricher import BaseEnricher, EnrichmentResult
from enrichments.common.models import Enrichment

logger = logging.getLogger(__name__)

# Rate limiting delay (seconds) before Zillow lookup
ZILLOW_DELAY = 5


class ZillowEnricher(BaseEnricher):
    """Enricher for Zillow property URLs and Zestimates."""

    enrichment_type = 'zillow'

    def enrich(self, case_id: int, force: bool = False) -> EnrichmentResult:
        """
        Enrich a case with Zillow URL and Zestimate.

        Args:
            case_id: Database ID of the case
            force: If True, re-enrich even if already enriched

        Returns:
            EnrichmentResult with success status, URL, and zestimate
        """
        with get_session() as session:
            case = session.get(Case, case_id)
            if not case:
                return EnrichmentResult(success=False, error=f"Case {case_id} not found")

            # Check if already enriched (unless force=True)
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not force and enrichment and enrichment.zillow_url:
                logger.info(f"Case {case.case_number} already has Zillow enrichment, skipping")
                return EnrichmentResult(
                    success=True,
                    url=enrichment.zillow_url,
                    account_id=str(enrichment.zillow_zestimate) if enrichment.zillow_zestimate else None
                )

            logger.info(f"Enriching case {case.case_number} with Zillow data")

            case_number = case.case_number
            property_address = case.property_address

        if not property_address:
            error = "No property_address available"
            logger.warning(f"Case {case_number}: {error}")
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

        return self._enrich_by_address(case_id, case_number, property_address)

    def _enrich_by_address(
        self,
        case_id: int,
        case_number: str,
        property_address: str
    ) -> EnrichmentResult:
        """Enrich using zillow_scraper lookup."""
        logger.info(f"Looking up Zillow for: {property_address}")

        # Rate limiting delay
        time.sleep(ZILLOW_DELAY)

        result = lookup(property_address)

        if isinstance(result, ZillowResult):
            # Success
            url = result.url
            zestimate = result.zestimate
            logger.info(f"Case {case_number}: Found Zillow URL, zestimate=${zestimate}")
            self._save_success(case_id, url, zestimate)
            return EnrichmentResult(
                success=True,
                url=url,
                account_id=str(zestimate) if zestimate else None
            )
        else:
            # ZillowError
            error = result.message or result.error
            logger.warning(f"Case {case_number}: Zillow lookup failed - {error}")
            self._save_error(case_id, error)
            return EnrichmentResult(success=False, error=error)

    def _save_success(self, case_id: int, url: str, zestimate: Optional[int]) -> None:
        """Save successful Zillow enrichment."""
        with get_session() as session:
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not enrichment:
                enrichment = Enrichment(case_id=case_id)
                session.add(enrichment)
            self._set_enrichment_fields(enrichment, url, zestimate, error=None)

    def _save_error(self, case_id: int, error: str) -> None:
        """Save Zillow enrichment error."""
        with get_session() as session:
            enrichment = session.query(Enrichment).filter_by(case_id=case_id).first()
            if not enrichment:
                enrichment = Enrichment(case_id=case_id)
                session.add(enrichment)
            self._set_enrichment_fields(enrichment, url=None, zestimate=None, error=error)

    def _set_enrichment_fields(
        self,
        enrichment: Enrichment,
        url: Optional[str],
        zestimate: Optional[int],
        error: Optional[str]
    ) -> None:
        """Set Zillow specific fields."""
        enrichment.zillow_url = url
        enrichment.zillow_zestimate = zestimate
        enrichment.zillow_error = error
        enrichment.zillow_enriched_at = datetime.now() if url else None
        enrichment.updated_at = datetime.now()


def enrich_case(case_id: int, force: bool = False) -> dict:
    """
    Convenience function for external calls.

    Args:
        case_id: Database ID of the case to enrich
        force: If True, re-enrich even if already enriched

    Returns:
        Dict with success status and enrichment data
    """
    enricher = ZillowEnricher()
    result = enricher.enrich(case_id, force=force)
    return result.to_dict()
```

**Step 3: Verify enricher loads**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from enrichments.zillow import enrich_case, ZillowEnricher; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add enrichments/zillow/
git commit -m "feat: add Zillow enricher"
```

---

## Task 4: Add Zillow to Router

**Files:**
- Modify: `enrichments/router.py`

**Step 1: Add Zillow import and call**

In `enrichments/router.py`, find the PropWire enrichment section (around line 91-93):

```python
    # PropWire enrichment (runs for ALL counties)
    from enrichments.prop_wire.enricher import enrich_case as propwire_enrich
    propwire_result = propwire_enrich(case_id)
```

Add after it:

```python
    # Zillow enrichment (runs for ALL counties)
    from enrichments.zillow.enricher import enrich_case as zillow_enrich
    zillow_result = zillow_enrich(case_id)
```

**Step 2: Update return statement**

Find the return statement (around line 95-98) and add zillow_result:

```python
    return {
        'county_re': county_result,
        'propwire': propwire_result,
        'zillow': zillow_result,
    }
```

**Step 3: Verify router loads**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from enrichments.router import enrich_case; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add enrichments/router.py
git commit -m "feat: add Zillow to enrichment router"
```

---

## Task 5: Add Zillow to API Responses

**Files:**
- Modify: `web_app/api/cases.py`

**Step 1: Add zillow fields to get_case response**

In `web_app/api/cases.py`, find the `get_case` function return statement (around line 283-289). Add after `deed_url`:

```python
            'zillow_url': enrichment.zillow_url if enrichment else None,
            'zillow_zestimate': enrichment.zillow_zestimate if enrichment else None,
```

**Step 2: Add zillow fields to get_upset_bids response**

In the same file, find the `get_upset_bids` function result.append (around line 523-530). Add after `deed_url`:

```python
            'zillow_url': enrichment.zillow_url if enrichment else None,
            'zillow_zestimate': enrichment.zillow_zestimate if enrichment else None,
```

**Step 3: Verify API loads**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from web_app.api.cases import cases_bp; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: add zillow fields to API responses"
```

---

## Task 6: Add Manual Trigger Endpoint

**Files:**
- Modify: `web_app/api/enrichments.py`

**Step 1: Add Zillow manual trigger endpoint**

In `web_app/api/enrichments.py`, add a new endpoint after the existing manual trigger endpoints:

```python
@enrichments_bp.route('/zillow/<int:case_id>', methods=['POST'])
@require_auth
def enrich_zillow(case_id):
    """Manually trigger Zillow enrichment for a case."""
    from enrichments.zillow.enricher import enrich_case

    force = request.json.get('force', False) if request.json else False
    result = enrich_case(case_id, force=force)

    return jsonify({
        'success': result.get('success', False),
        'url': result.get('url'),
        'zestimate': result.get('account_id'),  # account_id holds zestimate as string
        'error': result.get('error'),
    })
```

**Step 2: Verify endpoint loads**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) python -c "from web_app.api.enrichments import enrichments_bp; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add web_app/api/enrichments.py
git commit -m "feat: add Zillow manual trigger endpoint"
```

---

## Task 7: Update Frontend - Case Detail

**Files:**
- Modify: `frontend/src/pages/CaseDetail.jsx`

**Step 1: Update Zillow button to use enrichment URL**

In `frontend/src/pages/CaseDetail.jsx`, find the Zillow button (around lines 324-333):

```jsx
<Tooltip title={c.property_address ? "Search on Zillow" : "No address available"}>
  <Button
    size="small"
    icon={<ZillowIcon size={14} style={{ opacity: c.property_address ? 1 : 0.4 }} />}
    disabled={!c.property_address}
    onClick={() => c.property_address && window.open(formatZillowUrl(c.property_address), '_blank')}
  >
    Zillow
  </Button>
</Tooltip>
```

Replace with:

```jsx
<Tooltip title={
  c.zillow_url
    ? `Zillow${c.zillow_zestimate ? ` (Zestimate: $${c.zillow_zestimate.toLocaleString()})` : ''}`
    : c.property_address
      ? "Search on Zillow"
      : "No address available"
}>
  <Button
    size="small"
    icon={<ZillowIcon size={14} style={{ opacity: (c.zillow_url || c.property_address) ? 1 : 0.4 }} />}
    disabled={!c.zillow_url && !c.property_address}
    onClick={() => {
      const url = c.zillow_url || (c.property_address && formatZillowUrl(c.property_address));
      if (url) window.open(url, '_blank');
    }}
  >
    Zillow
  </Button>
</Tooltip>
```

**Step 2: Commit**

```bash
git add frontend/src/pages/CaseDetail.jsx
git commit -m "feat: use Zillow enrichment URL in case detail"
```

---

## Task 8: Update Frontend - Dashboard Zestimate Column

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`

**Step 1: Add Zestimate column to table**

In `frontend/src/pages/Dashboard.jsx`, find the columns definition (around line 205). Add a new column after the existing price-related columns (e.g., after current_bid or est_sale_price):

```jsx
{
  title: 'Zestimate',
  dataIndex: 'zillow_zestimate',
  key: 'zillow_zestimate',
  width: 100,
  sorter: (a, b) => (a.zillow_zestimate || 0) - (b.zillow_zestimate || 0),
  render: (value) => value ? `$${value.toLocaleString()}` : '-',
},
```

**Step 2: Update Zillow icon to use enrichment URL**

In the Links column render function (around lines 422-437), find the Zillow icon:

```jsx
<Tooltip title={hasAddress ? "Search on Zillow" : "No address available"}>
  <span
    onClick={(e) => {
      e.stopPropagation();
      if (hasAddress) window.open(formatZillowUrl(record.property_address), '_blank');
    }}
```

Replace with:

```jsx
<Tooltip title={
  record.zillow_url
    ? `View on Zillow${record.zillow_zestimate ? ` ($${record.zillow_zestimate.toLocaleString()})` : ''}`
    : hasAddress
      ? "Search on Zillow"
      : "No address available"
}>
  <span
    onClick={(e) => {
      e.stopPropagation();
      const url = record.zillow_url || (hasAddress && formatZillowUrl(record.property_address));
      if (url) window.open(url, '_blank');
    }}
```

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx
git commit -m "feat: add Zestimate column and use Zillow enrichment URL"
```

---

## Task 9: Integration Test

**Step 1: Start backend**

```bash
cd /home/ahn/projects/nc_foreclosures
source venv/bin/activate
sudo service postgresql start
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(host='0.0.0.0', port=5001)" &
```

**Step 2: Test manual Zillow enrichment**

Pick an upset_bid case with a property address and test:

```bash
# Get a case_id with property_address
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT id, case_number, property_address FROM cases WHERE classification='upset_bid' AND property_address IS NOT NULL LIMIT 1;"

# Trigger enrichment (replace CASE_ID)
curl -X POST http://localhost:5001/api/enrichments/zillow/CASE_ID -H "Content-Type: application/json"
```

Expected: JSON with success, url, zestimate (or error if property not found on Zillow)

**Step 3: Verify database**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT case_id, zillow_url, zillow_zestimate, zillow_error FROM enrichments WHERE zillow_url IS NOT NULL OR zillow_error IS NOT NULL LIMIT 5;"
```

**Step 4: Build and test frontend**

```bash
cd /home/ahn/projects/nc_foreclosures/frontend
npm run build
```

Expected: Build succeeds without errors

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete Zillow enrichment integration"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 0 | Install zillow_scraper | venv |
| 1 | Database migration | database/migrations/add_zillow_columns.sql |
| 2 | SQLAlchemy model | enrichments/common/models.py |
| 3 | Zillow enricher | enrichments/zillow/ |
| 4 | Router integration | enrichments/router.py |
| 5 | API responses | web_app/api/cases.py |
| 6 | Manual trigger endpoint | web_app/api/enrichments.py |
| 7 | Case detail frontend | frontend/src/pages/CaseDetail.jsx |
| 8 | Dashboard frontend | frontend/src/pages/Dashboard.jsx |
| 9 | Integration test | - |

---
