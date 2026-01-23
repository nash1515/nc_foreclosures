# Block During Upset Period Detection

**Date:** 2025-01-23
**Status:** Approved

## Problem

Case 25SP000679-910 was incorrectly classified as `closed_sold` when it should be `upcoming`.

**Timeline:**
- 07-30: Sale happened
- 08-22: Last upset bid (10-day window restarts)
- 08-25: Bankruptcy filed (only 3 days later - during upset period!)
- 11-04: Notice Of Sale/Resale (bankruptcy lifted, resale scheduled)

The classifier calculated "10 days from 08-22" and saw today > deadline → `closed_sold`. But the bankruptcy interrupted the upset period before it could complete. The sale never legally closed.

## Root Cause

The classifier only checks for bankruptcy if there's NO sale. It doesn't detect blocking events that occur DURING the upset bid period after a sale.

## Solution

Before declaring `closed_sold` (when past the calculated deadline), check if a blocking event interrupted the upset period:

1. Find any blocking event (bankruptcy, stay) dated AFTER the sale/last-upset-bid
2. If blocking event exists during the upset window:
   - Check if lifted (explicit lift event OR Notice Of Sale/Resale after block)
   - If lifted → `upcoming` (resale pending, continue monitoring)
   - If not lifted → `blocked` (still frozen, continue monitoring)
3. Only return `closed_sold` if NO blocking event interrupted the upset period

## Changes

**classifier.py:**

1. Add "Notice Of Sale/Resale" to `BANKRUPTCY_LIFTED_EVENTS` (resale notice implies block was lifted)

2. In the `closed_sold` path (after calculating deadline and finding it passed), add:
   ```python
   # Check if a blocking event interrupted the upset period
   blocking_event = get_latest_event_of_type(events, BLOCKING_EVENTS, exclusions=BANKRUPTCY_EXCLUSIONS)
   if blocking_event and blocking_event.event_date:
       block_date = blocking_event.event_date
       # Was the block during the upset period? (after reference_date, before deadline passed)
       if reference_date <= block_date <= adjusted_deadline:
           # Block interrupted the upset period - sale never completed
           lifted_event = get_latest_event_of_type(events, BANKRUPTCY_LIFTED_EVENTS)
           if lifted_event and lifted_event.event_date and lifted_event.event_date > block_date:
               # Block was lifted - case is upcoming (awaiting resale)
               return 'upcoming'
           else:
               # Block still active
               return 'blocked'
   ```

## Outcome

- Cases with blocking events during upset period stay monitored (`blocked` or `upcoming`)
- Only cases with uninterrupted upset periods become `closed_sold`
- Case 25SP000679-910 will correctly classify as `upcoming`
