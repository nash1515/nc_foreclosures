# Resale Detection Design

## Problem

When a foreclosure sale's high bidder fails to close, the court issues an "Order to Set Aside Sale" and the property goes back to auction. Our classifier doesn't detect this scenario - cases remain `closed_sold` when they should transition back to `upset_bid`.

**Example:** Case 24SP001381-910 had a $243k bid war, the winner defaulted, and the property resold for $7,317. We missed the opportunity because the case stayed `closed_sold`.

## Solution

Detect resales by checking if `closed_sold` cases have a new "Report of Sale" event with a date newer than the recorded `sale_date`. If so, reset the case and reclassify as `upset_bid`.

## Design

### Core Logic

```
When classifier runs on a case:

IF classification == 'closed_sold' AND sale_date exists:
    Find most recent "Report of Sale" event
    IF event_date > sale_date:
        → Resale detected
        → Return 'upset_bid' with new sale_date
        → Caller resets case data

ELSE:
    Normal classification logic (unchanged)
```

### Implementation Location

**File:** `extraction/classifier.py` in the `classify()` function

Add check at the start for `closed_sold` cases before running normal classification.

### Reset Actions (handled by caller)

When resale is detected:
1. Set `classification = upset_bid`
2. Set `sale_date` = new Report of Sale date
3. Extract `current_bid_amount` from new Report of Sale PDF (existing extraction logic)
4. Calculate `minimum_next_bid` = max(bid * 1.05, bid + 750)
5. Calculate `next_bid_deadline` = 10 business days from new sale_date
6. Clear stale data (old bid amounts are legally void)

### No New Extraction Needed

Existing Report of Sale PDF extraction handles the "Amount Bid" field. We reuse that logic for resale PDFs.

### No Special Flags

Event history already documents what happened (Order to Set Aside Sale, etc.). No need for a separate "resale" flag.

## Edge Cases

- **Multiple Report of Sale events:** Use the most recent by date
- **Same-day resale:** Unlikely, but date comparison handles it
- **Missing sale_date:** Skip resale check (can't compare without baseline)

## Testing

1. Use case 24SP001381-910 as test case
2. Verify classifier returns `upset_bid` when new Report of Sale exists
3. Verify bid amount extracted correctly from resale PDF
4. Verify deadline calculated from new sale date
