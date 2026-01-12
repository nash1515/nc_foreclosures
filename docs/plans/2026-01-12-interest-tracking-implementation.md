# Interest Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add "Interested? Yes/No" decision tracking to Case Detail with status icons on Dashboard.

**Architecture:** New `interest_status` column on cases table. Extend PATCH endpoint with validation. Add custom hurricane warning SVG. Dashboard shows review status icon before Links column.

**Tech Stack:** PostgreSQL, SQLAlchemy, Flask, React, Ant Design

---

## Task 1: Database Migration

**Files:**
- Create: `migrations/add_interest_status.sql`

**Step 1: Write migration SQL**

```sql
-- Add interest_status column to cases table
-- Values: NULL (not reviewed), 'interested', 'not_interested'
ALTER TABLE cases ADD COLUMN interest_status VARCHAR(20);

-- Add index for filtering by interest status
CREATE INDEX idx_cases_interest_status ON cases(interest_status);
```

**Step 2: Run migration**

Run:
```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f migrations/add_interest_status.sql
```

Expected: `ALTER TABLE` and `CREATE INDEX` success messages.

**Step 3: Verify column exists**

Run:
```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d cases" | grep interest_status
```

Expected: `interest_status | character varying(20)`

**Step 4: Commit**

```bash
git add migrations/add_interest_status.sql
git commit -m "feat: add interest_status column migration"
```

---

## Task 2: Update SQLAlchemy Model

**Files:**
- Modify: `database/models.py:79` (after team_notes field)

**Step 1: Add interest_status field to Case model**

After line 79 (`team_notes = Column(Text)`), add:

```python
    interest_status = Column(String(20))  # NULL, 'interested', 'not_interested'
```

**Step 2: Verify model loads**

Run:
```bash
cd /home/ahn/projects/nc_foreclosures && PYTHONPATH=$(pwd) python -c "from database.models import Case; print('interest_status' in [c.name for c in Case.__table__.columns])"
```

Expected: `True`

**Step 3: Commit**

```bash
git add database/models.py
git commit -m "feat: add interest_status field to Case model"
```

---

## Task 3: Update API - PATCH Endpoint with Validation

**Files:**
- Modify: `web_app/api/cases.py:554-606` (update_case function)

**Step 1: Add interest_status extraction and validation**

In the `update_case` function, after line 559 (`team_notes = data.get('team_notes')`), add:

```python
    interest_status = data.get('interest_status')
```

After line 565 (`return jsonify({'error': 'Case not found'}), 404`), add validation logic:

```python
        # Validate interest_status transitions
        if interest_status is not None:
            if interest_status == 'interested':
                # Check all required fields are filled
                # Use incoming values if provided, otherwise fall back to DB values
                est_price = estimated_sale_price if estimated_sale_price is not None else case.estimated_sale_price
                initial = our_initial_bid if our_initial_bid is not None else case.our_initial_bid
                second = our_second_bid if our_second_bid is not None else case.our_second_bid
                max_bid = our_max_bid if our_max_bid is not None else case.our_max_bid

                if not all([est_price, initial, second, max_bid]):
                    return jsonify({
                        'error': 'Complete Est. Sale Price and Bid Ladder before marking interested'
                    }), 400
            elif interest_status == 'not_interested':
                # Check team_notes has content
                notes = team_notes if team_notes is not None else case.team_notes
                if not notes or not notes.strip():
                    return jsonify({
                        'error': 'Add notes explaining why before marking not interested'
                    }), 400
            elif interest_status != '':  # Empty string means clear
                return jsonify({'error': 'Invalid interest_status value'}), 400
```

**Step 2: Add interest_status update logic**

After line 589 (`case.team_notes = team_notes`), add:

```python
        if interest_status is not None:
            # Empty string clears the status (back to not reviewed)
            case.interest_status = interest_status if interest_status else None
```

**Step 3: Add interest_status to response**

In the return jsonify block (around line 598), add after `'team_notes': case.team_notes`:

```python
            'interest_status': case.interest_status
```

**Step 4: Test validation - missing bid fields**

Run:
```bash
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{"interest_status": "interested"}' 2>/dev/null | python -m json.tool
```

Expected: `{"error": "Complete Est. Sale Price and Bid Ladder before marking interested"}`

**Step 5: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: add interest_status validation to PATCH endpoint"
```

---

## Task 4: Update API - Include interest_status in upset-bids response

**Files:**
- Modify: `web_app/api/cases.py:502-527` (upset-bids result building)

**Step 1: Add interest_status to response object**

In the `get_upset_bids` function, after line 526 (`'deed_url': enrichment.deed_url if enrichment else None`), add:

```python
                'interest_status': case.interest_status
```

**Step 2: Restart Flask to pick up changes**

Run:
```bash
# Kill existing Flask process and restart
pkill -f "python.*5001" || true
cd /home/ahn/projects/nc_foreclosures && PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(port=5001)" &
sleep 2
```

**Step 3: Verify endpoint includes new field**

Run:
```bash
curl -s http://localhost:5001/api/cases/upset-bids 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print('interest_status' in d['cases'][0] if d['cases'] else 'No cases')"
```

Expected: `True`

**Step 4: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: include interest_status in upset-bids response"
```

---

## Task 5: Create Hurricane Warning Flag SVG Component

**Files:**
- Create: `frontend/src/assets/HurricaneWarningIcon.jsx`

**Step 1: Create the SVG component**

```jsx
import React from 'react';

export const HurricaneWarningIcon = ({ size = 16, style = {} }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    style={style}
  >
    {/* Flag pole */}
    <line x1="4" y1="2" x2="4" y2="22" stroke="#666" strokeWidth="1.5" strokeLinecap="round" />

    {/* Red flag with wind-blown shape and frayed edge */}
    <path
      d="M4 3 C8 2, 12 4, 16 3 C18 2.5, 20 3, 22 4
         C21 5, 20 6, 21 7 C22 8, 21 9, 20 10
         C18 11, 16 10, 14 11 C12 12, 10 11, 8 12 C6 12.5, 5 12, 4 11
         L4 3Z"
      fill="#dc2626"
      stroke="#b91c1c"
      strokeWidth="0.5"
    />

    {/* Black square in center */}
    <rect x="9" y="5" width="5" height="4" fill="#1a1a1a" rx="0.3" />

    {/* Frayed edges (small triangular cuts) */}
    <path d="M20 10 L21 9.5 L20.5 10.5 Z" fill="#dc2626" />
    <path d="M21 7 L22 6.5 L21.5 7.5 Z" fill="#dc2626" />
    <path d="M22 4 L22.5 3.5 L22 5 Z" fill="#dc2626" />
  </svg>
);

export default HurricaneWarningIcon;
```

**Step 2: Verify component renders**

The component will be tested when integrated into Dashboard.

**Step 3: Commit**

```bash
git add frontend/src/assets/HurricaneWarningIcon.jsx
git commit -m "feat: add hurricane warning flag SVG icon"
```

---

## Task 6: Add Review Status Column to Dashboard

**Files:**
- Modify: `frontend/src/pages/Dashboard.jsx`

**Step 1: Add import for icons**

At line 10 (after existing icon imports), add `CloseCircleOutlined` to the imports if not already present:

```jsx
import {
  DollarOutlined, ClockCircleOutlined, HomeOutlined,
  WarningOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  StarOutlined, StarFilled, FileTextOutlined, CloseCircleOutlined
} from '@ant-design/icons';
```

**Step 2: Add import for HurricaneWarningIcon**

After line 17 (`import { GoogleMapsIcon } from '../assets/GoogleMapsIcon';`), add:

```jsx
import { HurricaneWarningIcon } from '../assets/HurricaneWarningIcon';
```

**Step 3: Add new column before Links column**

Before line 305 (the Links column `title: 'Links'`), insert:

```jsx
    {
      title: 'Review',
      key: 'review_status',
      width: 60,
      align: 'center',
      render: (_, record) => {
        if (record.interest_status === 'interested') {
          return (
            <Tooltip title="Interested">
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
            </Tooltip>
          );
        } else if (record.interest_status === 'not_interested') {
          return (
            <Tooltip title="Not Interested">
              <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />
            </Tooltip>
          );
        } else {
          return (
            <Tooltip title="Not Reviewed">
              <HurricaneWarningIcon size={18} style={{ display: 'block', margin: '0 auto' }} />
            </Tooltip>
          );
        }
      }
    },
```

**Step 4: Verify Dashboard loads with new column**

Open browser to http://localhost:5173 and verify:
- New "Review" column appears before Links
- Hurricane warning icon shows for cases without interest_status

**Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.jsx
git commit -m "feat: add review status column to Dashboard"
```

---

## Task 7: Add Analysis Decision Card to Case Detail

**Files:**
- Modify: `frontend/src/pages/CaseDetail.jsx`

**Step 1: Add state for interest status and error**

After the existing state declarations (around line 30), find where other state is declared and add:

```jsx
const [interestStatus, setInterestStatus] = useState(null);
const [interestError, setInterestError] = useState(null);
const [interestSaving, setInterestSaving] = useState(false);
```

**Step 2: Initialize interestStatus from caseData**

In the useEffect that processes caseData (or where other fields are initialized from API response), add:

```jsx
setInterestStatus(data.interest_status || null);
```

**Step 3: Add handler function for interest status changes**

Add this function near other handlers (like handleNotesSave):

```jsx
const handleInterestChange = async (newStatus) => {
  setInterestError(null);

  // If clicking the same status, clear it (toggle off)
  const statusToSet = newStatus === interestStatus ? '' : newStatus;

  setInterestSaving(true);
  try {
    const response = await fetch(`/api/cases/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ interest_status: statusToSet })
    });

    const data = await response.json();

    if (!response.ok) {
      setInterestError(data.error || 'Failed to update');
      return;
    }

    setInterestStatus(data.interest_status || null);
  } catch (err) {
    setInterestError('Network error');
  } finally {
    setInterestSaving(false);
  }
};
```

**Step 4: Add Analysis Decision card after AI Analysis Section**

After line 493 (the closing `</div>` of AI Analysis Section), add:

```jsx
      {/* Analysis Decision */}
      <Card title="Analysis Decision" style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center' }}>
          <Space size="middle">
            <Text strong>Interested?</Text>
            <Button
              type={interestStatus === 'interested' ? 'primary' : 'default'}
              style={interestStatus === 'interested' ? {
                backgroundColor: '#52c41a',
                borderColor: '#52c41a'
              } : {}}
              onClick={() => handleInterestChange('interested')}
              loading={interestSaving}
            >
              Yes
            </Button>
            <Button
              type={interestStatus === 'not_interested' ? 'primary' : 'default'}
              danger={interestStatus === 'not_interested'}
              onClick={() => handleInterestChange('not_interested')}
              loading={interestSaving}
            >
              No
            </Button>
          </Space>
          {interestError && (
            <div style={{ marginTop: 12 }}>
              <Text type="danger">{interestError}</Text>
            </div>
          )}
        </div>
      </Card>
```

**Step 5: Add Button import if not present**

Verify `Button` is in the antd imports at the top of the file.

**Step 6: Verify Case Detail page loads and shows Analysis Decision card**

Open browser to http://localhost:5173/cases/1 and verify:
- Analysis Decision card appears below AI Analysis
- Yes/No buttons are visible
- Clicking Yes without bid fields shows error message

**Step 7: Commit**

```bash
git add frontend/src/pages/CaseDetail.jsx
git commit -m "feat: add Analysis Decision card to Case Detail"
```

---

## Task 8: Update API - Include interest_status in case detail response

**Files:**
- Modify: `web_app/api/cases.py` (get_case function, around line 181-288)

**Step 1: Find the case detail response and add interest_status**

In the `get_case` function, find where the response dict is built and add:

```python
'interest_status': case.interest_status,
```

**Step 2: Verify case detail includes interest_status**

Run:
```bash
curl -s http://localhost:5001/api/cases/1 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print('interest_status:', d.get('interest_status'))"
```

Expected: `interest_status: None` (or the actual value if set)

**Step 3: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: include interest_status in case detail response"
```

---

## Task 9: End-to-End Testing

**Step 1: Test complete flow - Set all required fields**

```bash
# First, set all required fields on a test case
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{
    "estimated_sale_price": 200000,
    "our_initial_bid": 100000,
    "our_second_bid": 110000,
    "our_max_bid": 120000
  }' 2>/dev/null | python -m json.tool
```

**Step 2: Test setting interested status**

```bash
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{"interest_status": "interested"}' 2>/dev/null | python -m json.tool
```

Expected: Response includes `"interest_status": "interested"`

**Step 3: Verify Dashboard shows green check**

Refresh http://localhost:5173 - case should show green check in Review column.

**Step 4: Test clearing status**

```bash
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{"interest_status": ""}' 2>/dev/null | python -m json.tool
```

Expected: Response includes `"interest_status": null`

**Step 5: Test not_interested with notes**

```bash
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{"team_notes": "Property condition too poor", "interest_status": "not_interested"}' 2>/dev/null | python -m json.tool
```

Expected: Response includes `"interest_status": "not_interested"`

**Step 6: Verify Dashboard shows red X**

Refresh http://localhost:5173 - case should show red X in Review column.

**Step 7: Final commit**

```bash
git add -A
git commit -m "feat: complete interest tracking feature

- Add interest_status column to cases table
- Add validation: interested requires bid fields, not_interested requires notes
- Add hurricane warning flag SVG for not-reviewed state
- Add Review column to Dashboard with status icons
- Add Analysis Decision card to Case Detail page"
```

---

## Summary of Files Modified

| File | Change |
|------|--------|
| `migrations/add_interest_status.sql` | New migration |
| `database/models.py` | Add interest_status field |
| `web_app/api/cases.py` | Add validation + include in responses |
| `frontend/src/assets/HurricaneWarningIcon.jsx` | New SVG component |
| `frontend/src/pages/Dashboard.jsx` | Add Review column |
| `frontend/src/pages/CaseDetail.jsx` | Add Analysis Decision card |
