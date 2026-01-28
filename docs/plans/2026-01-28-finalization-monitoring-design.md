# Finalization-Based Case Monitoring Design

**Date:** 2026-01-28
**Status:** Approved
**Problem:** Closed/blocked cases can reopen but aren't monitored, causing missed opportunities

## Problem Statement

Current monitoring only includes cases with `classification IN ('upcoming', 'blocked', 'upset_bid')`. This misses:
- **426 closed_sold** cases that could have sales set aside
- **99 closed_dismissed** cases that could be reinstated
- **69 blocked** cases (actually monitored, but complex unblocking logic is fragile)

Real example: Case 17SP003010-910 reopened after 5 years with new sale and upset bids - we missed it.

## Solution: Binary Finalization Model

Replace classification-based monitoring with a simple binary flag:

| `is_finalized` | Meaning | Action |
|----------------|---------|--------|
| `FALSE` | Case could still have activity | Monitor daily |
| `TRUE` | Court has closed the case | Never monitor again |

### Finalization Events

Only these events indicate a case is truly closed:
- Order Confirming Sale / Order of Confirmation
- Final Report of Sale / Commissioner's Final Report
- Final Account
- Order for Disbursement
- Settlement Statement

## Database Changes

```sql
ALTER TABLE cases ADD COLUMN is_finalized BOOLEAN DEFAULT FALSE;
ALTER TABLE cases ADD COLUMN finalized_at TIMESTAMP NULL;
ALTER TABLE cases ADD COLUMN finalized_event_id INTEGER NULL;
```

- Keep all existing fields (`classification`, `closed_sold_at`, etc.) for reporting
- ~160 existing cases will be backfilled as finalized

## Monitoring Changes

### Current (1,836 cases/day)
```python
Case.classification.in_(['upcoming', 'blocked', 'upset_bid'])
```

### New (2,223 cases/day)
```python
Case.is_finalized == False,
Case.case_url.isnot(None)
```

**Impact:** +387 cases/day (+21%), but zero risk of missing reopened cases.

## Code Removal

These tasks become obsolete:
- **Task 7:** Grace Period Monitoring (5-day closed_sold re-check)
- **Task 8:** Set-Aside Case Monitoring (daily re-check of set-aside cases)
- **Task 9:** Weekly Closed_Sold Scan (Friday full scan)

All replaced by: monitor everything that isn't finalized.

## Implementation Steps

1. Database migration - add three new columns
2. Add finalization detection in `classifier.py`
3. Backfill script - mark existing finalized cases
4. Update `get_cases_to_monitor()` filter
5. Update `process_case()` to detect and mark finalization
6. Remove Tasks 7, 8, 9 from `daily_scrape.py`
7. Update task numbering and logging

## Success Criteria

- [ ] 160 cases backfilled as finalized
- [ ] Daily monitoring includes ~2,223 cases
- [ ] Finalization detection works on new events
- [ ] No monitoring errors after changes
- [ ] Case 17SP003010-910 (and similar) now monitored
