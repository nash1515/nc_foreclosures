# Interest Tracking Feature Design

**Date:** 2026-01-12
**Status:** Approved

## Overview

Track whether cases have been manually analyzed with an "Interested? Yes/No" decision. Display analysis status on Dashboard with distinctive icons.

## Three States

| State | Dashboard Icon | Meaning |
|-------|----------------|---------|
| Not reviewed | Hurricane warning flag (red flag, black square, wind-blown, frayed edge) | Haven't decided yet |
| Interested | Green check (`CheckCircleOutlined`) | Yes, pursuing this case |
| Not Interested | Red X (`CloseCircleOutlined`) | No, passing on this case |

## Data Model

**New column on `cases` table:**

```sql
ALTER TABLE cases ADD COLUMN interest_status VARCHAR(20);
-- Values: NULL (not reviewed), 'interested', 'not_interested'
```

**Model update:**
```python
interest_status = Column(String(20), nullable=True, default=None)
```

## API Layer

**Extend PATCH `/api/cases/<case_id>`:**

Add `interest_status` to allowed fields with server-side validation:

### Validation for "interested"
Required fields (all must be non-null):
- `estimated_sale_price`
- `our_initial_bid`
- `our_second_bid`
- `our_max_bid`

Error message: "Complete Est. Sale Price and Bid Ladder before marking interested"

### Validation for "not_interested"
Required fields:
- `team_notes` (must have non-empty text)

Error message: "Add notes explaining why before marking not interested"

### Response
Returns updated case with `interest_status` field.

### Upset-bids endpoint
Include `interest_status` in response (already returns full case data).

## Case Detail UI

### Placement
New card titled "Analysis Decision" below Team Notes card.

### Layout
```
┌─────────────────────────────────────────────────┐
│ Analysis Decision                               │
├─────────────────────────────────────────────────┤
│                                                 │
│   Interested?    [Yes]    [No]                  │
│                                                 │
│   (error message appears here - red text)       │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Button Behavior
- Toggle-style buttons (like radio buttons visually)
- Active Yes = green background
- Active No = red background
- Inactive = neutral/gray outline
- **Clicking already-selected button clears it** (reverts to "not reviewed")

### Validation Flow
1. User clicks Yes or No
2. Frontend checks required fields
3. If validation fails: show red error text below buttons
4. If validation passes: API call, button becomes active
5. Error clears when user starts fixing the issue

## Dashboard UI

### New Column
- **Name:** "Review" (or icon-only header)
- **Position:** Before Links column (second-to-last)
- **Behavior:** Display only (no click action)

### Icons

| State | Icon | Color |
|-------|------|-------|
| Not reviewed | Custom hurricane warning flag SVG | Orange/amber |
| Interested | `CheckCircleOutlined` | Green (#52c41a) |
| Not Interested | `CloseCircleOutlined` | Red (#ff4d4f) |

### Hurricane Warning Flag SVG
Custom SVG depicting the maritime hurricane warning signal:
- Red flag with black square in center
- Wind-blown appearance (billowing shape)
- Frayed/ragged trailing edge
- Recognizable at ~16px size

## Files to Modify

1. `database/models.py` - Add `interest_status` field to Case class
2. `migrations/add_interest_status.sql` - Database migration
3. `web_app/api/cases.py` - Add validation logic to PATCH endpoint, include in upset-bids response
4. `frontend/src/pages/CaseDetail.jsx` - Add Analysis Decision card
5. `frontend/src/pages/Dashboard.jsx` - Add Review column with icons
6. `frontend/src/assets/` or inline - Hurricane warning flag SVG

## Error Messages

| Trigger | Message |
|---------|---------|
| Yes clicked, missing bid fields | "Complete Est. Sale Price and Bid Ladder before marking interested" |
| No clicked, notes empty | "Add notes explaining why before marking not interested" |
