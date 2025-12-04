# Classification Enhancement Design

**Date:** 2025-12-04
**Status:** Draft
**Problem:** Non-foreclosure sale cases (ward's estate, tax liens, receivership, etc.) with upset bid opportunities are not being captured by the daily scrape.

## Background

Case 25SP001546-910 (Ward's Estate sale) was missed on day 1 because:
- Case type = "Special Proceeding" (not "Foreclosure")
- Event types were generic: "Petition", "Special Proceedings Summons", "Notice (General)"
- The key indicator was in the **document title**: "Petition to Sell/Lease/Mortgage Ward's Estate"

NC law provides 10-day upset bid rights for 7 types of court-ordered sales:
1. Foreclosure (power-of-sale) - **Currently detected**
2. Partition Sale - **Currently detected** (added Session 14)
3. Tax Foreclosure
4. Receivership Sale
5. Estate Sale (decedent's property)
6. Guardianship/Ward's Sale
7. Trust Property Sale

Types 3-7 are currently missed because we only check event types, not document titles.

## Solution Overview

**Approach:** Enhanced detection with human-in-the-loop approval

1. Add document title pattern matching to capture potential sale cases
2. Log ALL examined cases (saved and skipped) during daily scrape
3. Present daily review queue in frontend for manual verification
4. Approved cases become `upcoming`, rejected cases are deleted

This hybrid approach allows aggressive detection without database bloat, while building confidence in the detection patterns over time.

## Detailed Design

### 1. New Detection Indicators

Add to `scraper/page_parser.py`:

```python
# Document title patterns that indicate a potential sale with upset bid rights
SALE_DOCUMENT_INDICATORS = [
    "petition to sell",
    "petition to lease",
    "petition to mortgage",
    "ward's estate",
    "incompetent's estate",
    "minor's estate",
    "decedent's estate",
    "sell real property",
    "tax lien foreclosure",
    "tax foreclosure",
    "delinquent tax",
    "receivership",
    "receiver's sale",
    "trust property sale",
    "sell trust property",
]
```

### 2. Enhanced Case Detection

Modify `is_foreclosure_case()` to check:
1. Case type contains "foreclosure" (existing)
2. Event types match `FORECLOSURE_EVENT_INDICATORS` (existing)
3. Event types match `UPSET_BID_OPPORTUNITY_INDICATORS` (existing)
4. **NEW:** Document titles match `SALE_DOCUMENT_INDICATORS`

Modify `parse_case_detail()` to capture document titles from events (currently only captures event types).

### 3. Database Changes

**New table: `skipped_cases`**

```sql
CREATE TABLE skipped_cases (
    id SERIAL PRIMARY KEY,
    case_number VARCHAR(50) NOT NULL,
    county_code VARCHAR(10) NOT NULL,
    county_name VARCHAR(50) NOT NULL,
    case_url TEXT,
    case_type VARCHAR(100),
    style TEXT,
    file_date DATE,
    events_json JSONB,  -- Store events with document titles for review
    skip_reason VARCHAR(255),
    scrape_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    review_action VARCHAR(20)  -- 'added', 'dismissed', NULL (pending)
);

CREATE INDEX idx_skipped_cases_scrape_date ON skipped_cases(scrape_date);
CREATE INDEX idx_skipped_cases_reviewed ON skipped_cases(reviewed_at);
```

**New model in `database/models.py`:**

```python
class SkippedCase(Base):
    __tablename__ = 'skipped_cases'

    id = Column(Integer, primary_key=True)
    case_number = Column(String(50), nullable=False)
    county_code = Column(String(10), nullable=False)
    county_name = Column(String(50), nullable=False)
    case_url = Column(Text)
    case_type = Column(String(100))
    style = Column(Text)
    file_date = Column(Date)
    events_json = Column(JSONB)
    skip_reason = Column(String(255))
    scrape_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    review_action = Column(String(20))
```

### 4. Scraper Changes

**Modify `scraper/date_range_scrape.py`:**

In `_process_case_in_new_tab()`:
- If `is_foreclosure_case()` returns True → save to `cases` table (existing behavior)
- If returns False → save to `skipped_cases` table with `skip_reason`

```python
if is_foreclosure_case(case_data):
    self._save_case(case_number, case_url, county_code, county_name, case_data)
else:
    self._save_skipped_case(case_number, case_url, county_code, county_name, case_data,
                            skip_reason="No foreclosure or sale indicators detected")
```

### 5. API Endpoints

**New endpoints in `web_app/api/review.py`:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/review/daily?date=YYYY-MM-DD` | Get foreclosures + skipped for date |
| POST | `/api/review/foreclosures/reject` | Bulk reject (delete) foreclosure cases |
| POST | `/api/review/skipped/add` | Bulk add skipped cases as foreclosures |
| POST | `/api/review/skipped/dismiss` | Bulk dismiss skipped cases |
| DELETE | `/api/review/cleanup?days=7` | Remove old dismissed skipped cases |

**Response format for GET `/api/review/daily`:**

```json
{
  "date": "2025-12-04",
  "foreclosures": [
    {
      "id": 1832,
      "case_number": "25SP002738-910",
      "county_name": "Wake",
      "case_type": "Foreclosure (Special Proceeding)",
      "style": "FORECLOSURE OF A DEED OF TRUST Eugene Delosh",
      "file_date": "2025-12-03",
      "events": [
        {"event_date": "2025-12-03", "event_type": "Petition", "document_title": "..."}
      ]
    }
  ],
  "skipped": [
    {
      "id": 45,
      "case_number": "25SP002735-910",
      "county_name": "Wake",
      "case_type": "Special Proceeding",
      "style": null,
      "file_date": "2025-12-03",
      "skip_reason": "No foreclosure or sale indicators detected",
      "events": [...]
    }
  ],
  "counts": {
    "foreclosures": 3,
    "skipped": 12,
    "pending_review": 15
  }
}
```

### 6. Frontend Design

**New "Review Queue" tab in navigation**

Badge shows pending count: `Review Queue (15)`

**Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Review Queue                          Date: [Dec 04, 2025 ▼]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ▼ Foreclosures (3 cases)                    [Bulk Actions ▼]  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ☐ │ Case Number    │ County │ Style            │ Action  │  │
│  ├───┼────────────────┼────────┼──────────────────┼─────────┤  │
│  │ ☐ │ 25SP002738-910 │ Wake   │ FORECLOSURE -... │ [Reject]│  │
│  │ ☐ │ 25SP002739-910 │ Wake   │ FORECLOSURE -... │ [Reject]│  │
│  │ ☐ │ 25SP002740-910 │ Wake   │ FORECLOSURE -... │ [Reject]│  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ▼ Skipped (12 cases)                        [Bulk Actions ▼]  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ☐ │ Case Number    │ County │ Case Type    │ Reason │Act │  │
│  ├───┼────────────────┼────────┼──────────────┼────────┼────┤  │
│  │ ☐ │ 25SP002735-910 │ Wake   │ Special Proc │ No ind │[Add]│  │
│  │ ☐ │ 25SP002736-310 │ Durham │ Special Proc │ No ind │[Add]│  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**
- Date picker (defaults to today, can review past days)
- Expandable rows showing events/documents
- Checkbox selection for bulk operations
- Bulk actions dropdown per section:
  - Foreclosures: "Confirm All", "Reject Selected"
  - Skipped: "Add Selected", "Dismiss All"

**Row expansion (click to view):**
```
│ ▼ 25SP002735-910 │ Wake │ Special Proceeding │ No indicators │
│   ├─ Events:                                                  │
│   │   • 12/03/2025 - Petition (Doc: Petition to Sell Ward's..)│
│   │   • 12/03/2025 - Special Proceedings Summons              │
│   │   • 12/03/2025 - Notice (General)                         │
│   └─ [Add to Foreclosures] [Dismiss]                          │
```

### 7. Data Retention

- Skipped cases with `review_action = 'dismissed'` are deleted after 7 days
- Cleanup runs automatically during daily scrape or via API endpoint
- Prevents unbounded growth of `skipped_cases` table

### 8. Daily Scrape Integration

**Modified workflow in `scraper/daily_scrape.py`:**

1. Task 1: Search for new cases filed yesterday
2. Task 2: For each case:
   - Parse case details including document titles
   - If foreclosure detected → save to `cases` table
   - If not detected → save to `skipped_cases` table
3. Task 3: Monitor existing `upcoming`, `blocked`, `upset_bid` cases
4. Task 4: Cleanup old dismissed skipped cases (7+ days)

**No changes to case monitoring** - only newly scraped cases go through review.

## Implementation Plan

### Phase 1: Backend (Detection + Database)
1. Add `skipped_cases` table and model
2. Add `SALE_DOCUMENT_INDICATORS` to page_parser.py
3. Modify `parse_case_detail()` to capture document titles
4. Modify `is_foreclosure_case()` to check document titles
5. Modify `date_range_scrape.py` to log skipped cases

### Phase 2: API
1. Create `web_app/api/review.py` with endpoints
2. Register blueprint in `web_app/app.py`
3. Add cleanup task to daily scrape

### Phase 3: Frontend
1. Create Review Queue page component
2. Add data tables with expandable rows
3. Implement checkbox selection and bulk actions
4. Add date picker and navigation badge

## Success Criteria

1. Ward's Estate case (25SP001546-910 pattern) would be captured
2. All SP cases examined during daily scrape are logged (saved or skipped)
3. User can review and override system decisions
4. No database bloat from rejected/dismissed cases
5. Detection patterns can be refined based on review feedback

## Future Enhancements

- Track which patterns triggered detection (for refinement)
- Export review decisions to train better detection
- Auto-approve patterns after N consecutive approvals
- Email notification when review queue has items
