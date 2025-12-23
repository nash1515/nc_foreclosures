# Grace Period Monitoring for Closed Sold Cases

**Date:** 2025-12-23
**Status:** Approved
**Problem:** Case 25SP002519-910 had an upset bid filed on 12/22 but system missed it because case was already classified as `closed_sold`

## Problem Statement

Once a case is classified as `closed_sold` (after the 10-day upset period expires), it is completely excluded from daily monitoring. Late-filed events like:
- **Upset Bid Filed** - new upset bid
- **Report of Sale** - someone won previous bid round (resets 10-day clock)

...are never detected, causing missed investment opportunities.

## Root Cause

`scraper/case_monitor.py:90-97` only monitors cases with classification in `['upcoming', 'blocked', 'upset_bid']`. The 358+ `closed_sold` cases are never checked again.

## Solution: Grace Period Monitoring

Add a 5-day grace period after cases transition to `closed_sold`. During this window, cases continue to be monitored for new sale-related events.

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Grace period duration | 5 days | Covers business week, catches 99%+ of late filings |
| Monitoring behavior | Full re-monitor | Ensures all data is current after being stale |
| Timestamp tracking | New `closed_sold_at` column | Explicit, queryable, not affected by other updates |

## Implementation

### 1. Database Schema Change

**Migration:** `migrations/add_closed_sold_at.sql`

```sql
ALTER TABLE cases ADD COLUMN closed_sold_at TIMESTAMP;

CREATE INDEX idx_cases_closed_sold_at ON cases (closed_sold_at)
WHERE classification = 'closed_sold' AND closed_sold_at IS NOT NULL;
```

### 2. Model Update

**File:** `database/models.py`

Add `closed_sold_at = Column(DateTime)` to Case model.

### 3. Classification Timestamp Logic

**File:** `scraper/case_monitor.py` (where classification is applied)

```python
old_classification = case.classification
new_classification = classify_case(case, events, ...)

if new_classification == 'closed_sold' and old_classification != 'closed_sold':
    case.closed_sold_at = datetime.now()
elif new_classification != 'closed_sold' and old_classification == 'closed_sold':
    case.closed_sold_at = None

case.classification = new_classification
```

### 4. New Daily Scrape Task

**File:** `scraper/daily_scrape.py`

**Task 7: Grace Period Monitoring**

```python
def run_grace_period_monitoring(session, task_logger):
    """Monitor recently-closed cases for late upset bids."""
    GRACE_PERIOD_DAYS = 5
    cutoff = datetime.now() - timedelta(days=GRACE_PERIOD_DAYS)

    grace_period_cases = session.query(Case).filter(
        Case.classification == 'closed_sold',
        Case.closed_sold_at.isnot(None),
        Case.closed_sold_at >= cutoff,
        Case.case_url.isnot(None)
    ).all()

    # Full re-monitor each case
    # If new events found, reclassification happens automatically
```

## Files to Modify

| File | Change |
|------|--------|
| `migrations/add_closed_sold_at.sql` | NEW - Add column + index |
| `database/models.py` | Add `closed_sold_at` to Case model |
| `scraper/case_monitor.py` | Add timestamp logic when applying classification |
| `scraper/daily_scrape.py` | Add Task 7 for grace period monitoring |

## Testing

1. Manually trigger grace period monitoring
2. Verify case 25SP002519-910 gets reactivated
3. Verify `closed_sold_at` is set/cleared correctly on classification changes
4. Verify old `closed_sold` cases (NULL timestamp) are not monitored

## Estimated Scope

~50-80 lines of code across 4 files.
