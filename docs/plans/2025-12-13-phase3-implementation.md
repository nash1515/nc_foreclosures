# Phase 3: Collaboration Features - Implementation Plan

**Date:** December 13, 2025
**Design Doc:** `docs/plans/2025-12-13-phase3-collaboration-design.md`
**Target:** Add shared notes and bid ladder editing to Case Detail page

---

## Overview

This plan breaks down Phase 3 into 8 executable tasks. Each task is independent and includes exact file paths, complete code, and verification steps. The engineer needs **zero codebase context** - everything is provided.

**Key Design Principles:**
- All collaboration data lives on the `cases` table (no new tables)
- Auto-save with 1.5s debounce for minimal friction
- Simple UI - no edit history or complex permissions
- Last write wins for concurrent edits

---

## Task 1: Database Migration

**Goal:** Add 4 collaboration fields to the `cases` table.

### Files to Modify

**File:** `/home/ahn/projects/nc_foreclosures/migrations/add_collaboration_fields.sql` (NEW)

**Content:**
```sql
-- Add collaboration fields to cases table
ALTER TABLE cases ADD COLUMN IF NOT EXISTS our_initial_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS our_second_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS our_max_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS team_notes TEXT;

-- Add index for cases with team notes
CREATE INDEX IF NOT EXISTS idx_cases_team_notes
ON cases(id)
WHERE team_notes IS NOT NULL;
```

**File:** `/home/ahn/projects/nc_foreclosures/database/models.py`

**What to Change:** Add 4 new columns to the `Case` class after line 72 (`attorney_email`).

**Code to Add:**
```python
    # Collaboration fields (Phase 3)
    our_initial_bid = Column(DECIMAL(12, 2))
    our_second_bid = Column(DECIMAL(12, 2))
    our_max_bid = Column(DECIMAL(12, 2))
    team_notes = Column(Text)
```

**Result:** The `Case` class should now have these fields between `attorney_email` and `reviewed_at`.

### How to Verify

```bash
# 1. Run the migration
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost \
  -f /home/ahn/projects/nc_foreclosures/migrations/add_collaboration_fields.sql

# 2. Verify columns exist
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost \
  -c "\d cases" | grep -E "(our_initial_bid|our_second_bid|our_max_bid|team_notes)"

# Expected output:
# our_initial_bid        | numeric(12,2)    |
# our_second_bid         | numeric(12,2)    |
# our_max_bid            | numeric(12,2)    |
# team_notes             | text             |

# 3. Test SQLAlchemy model loads
cd /home/ahn/projects/nc_foreclosures
source venv/bin/activate
export PYTHONPATH=$(pwd)
python -c "from database.models import Case; print('Model loaded successfully')"

# Expected output: "Model loaded successfully"
```

---

## Task 2: Backend API Endpoint

**Goal:** Create `PATCH /api/cases/<id>` endpoint to update collaboration fields.

### Files to Modify

**File:** `/home/ahn/projects/nc_foreclosures/web_app/api/cases.py`

**What to Add:** Add new endpoint at the end of the file (after line 493).

**Code to Add:**
```python
@cases_bp.route('/<int:case_id>', methods=['PATCH'])
def update_case(case_id):
    """Update case collaboration fields.

    Request body (all fields optional):
    {
        "our_initial_bid": 50000,
        "our_second_bid": 55000,
        "our_max_bid": 60000,
        "team_notes": "Property looks good. Needs roof work (~15k)."
    }
    """
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    # Parse request body
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Extract allowed fields
    our_initial_bid = data.get('our_initial_bid')
    our_second_bid = data.get('our_second_bid')
    our_max_bid = data.get('our_max_bid')
    team_notes = data.get('team_notes')

    # Validate bid ladder if any bids provided
    if our_initial_bid is not None or our_second_bid is not None or our_max_bid is not None:
        # Convert to float for comparison (handle None values)
        initial = float(our_initial_bid) if our_initial_bid is not None else None
        second = float(our_second_bid) if our_second_bid is not None else None
        max_bid = float(our_max_bid) if our_max_bid is not None else None

        # Validate ordering if all three are set
        if initial is not None and second is not None and max_bid is not None:
            if not (initial <= second <= max_bid):
                return jsonify({
                    'error': 'Invalid bid ladder: our_initial_bid <= our_second_bid <= our_max_bid'
                }), 400

    with get_session() as db_session:
        # Fetch case
        case = db_session.query(Case).filter_by(id=case_id).first()
        if not case:
            return jsonify({'error': 'Case not found'}), 404

        # Update fields (only if provided in request)
        if our_initial_bid is not None:
            case.our_initial_bid = our_initial_bid
        if our_second_bid is not None:
            case.our_second_bid = our_second_bid
        if our_max_bid is not None:
            case.our_max_bid = our_max_bid
        if team_notes is not None:
            case.team_notes = team_notes

        db_session.commit()

        # Return updated case (reuse existing serialization logic)
        user_id = get_current_user_id()
        is_watchlisted = False
        if user_id:
            watchlist = db_session.query(Watchlist).filter_by(
                user_id=user_id, case_id=case_id
            ).first()
            is_watchlisted = watchlist is not None

        # Get parties grouped by type
        parties = {}
        for party in case.parties:
            party_type = party.party_type
            if party_type not in parties:
                parties[party_type] = []
            parties[party_type].append(party.party_name)

        # Get events sorted by date
        events = []
        for event in sorted(case.events, key=lambda e: e.event_date or datetime.min.date(), reverse=True):
            events.append({
                'id': event.id,
                'date': event.event_date.isoformat() if event.event_date else None,
                'type': event.event_type,
                'description': event.event_description,
                'filed_by': event.filed_by,
                'filed_against': event.filed_against,
                'document_url': event.document_url
            })

        # Get hearings
        hearings = []
        for hearing in case.hearings:
            hearings.append({
                'id': hearing.id,
                'date': hearing.hearing_date.isoformat() if hearing.hearing_date else None,
                'time': hearing.hearing_time,
                'type': hearing.hearing_type
            })

        # Extract upset bidders
        upset_bidders = []
        for event in case.events:
            if event.event_type and 'upset' in event.event_type.lower():
                upset_bidders.append({
                    'date': event.event_date.isoformat() if event.event_date else None,
                    'bidder': event.filed_by or 'Unknown',
                    'amount': None
                })

        return jsonify({
            'id': case.id,
            'case_number': case.case_number,
            'county_code': case.county_code,
            'county_name': case.county_name,
            'case_type': case.case_type,
            'case_status': case.case_status,
            'style': case.style,
            'classification': case.classification,
            'file_date': case.file_date.isoformat() if case.file_date else None,
            'case_url': case.case_url,
            'property_address': case.property_address,
            'current_bid_amount': float(case.current_bid_amount) if case.current_bid_amount else None,
            'minimum_next_bid': float(case.minimum_next_bid) if case.minimum_next_bid else None,
            'next_bid_deadline': case.next_bid_deadline.isoformat() if case.next_bid_deadline else None,
            'sale_date': case.sale_date.isoformat() if case.sale_date else None,
            'legal_description': case.legal_description,
            'trustee_name': case.trustee_name,
            'attorney_name': case.attorney_name,
            'attorney_phone': case.attorney_phone,
            'attorney_email': case.attorney_email,
            'our_initial_bid': float(case.our_initial_bid) if case.our_initial_bid else None,
            'our_second_bid': float(case.our_second_bid) if case.our_second_bid else None,
            'our_max_bid': float(case.our_max_bid) if case.our_max_bid else None,
            'team_notes': case.team_notes,
            'parties': parties,
            'events': events,
            'hearings': hearings,
            'upset_bidders': upset_bidders,
            'is_watchlisted': is_watchlisted,
            'photo_url': None
        })
```

**What to Modify:** Update the existing `GET /api/cases/<id>` endpoint (line 173) to include new fields in response.

**Find this code block (lines 237-264):**
```python
        return jsonify({
            'id': case.id,
            'case_number': case.case_number,
            # ... existing fields ...
            'upset_bidders': upset_bidders,
            'is_watchlisted': is_watchlisted,
            'photo_url': None  # Placeholder for future enrichment
        })
```

**Replace the `return jsonify({...})` block with:**
```python
        return jsonify({
            'id': case.id,
            'case_number': case.case_number,
            'county_code': case.county_code,
            'county_name': case.county_name,
            'case_type': case.case_type,
            'case_status': case.case_status,
            'style': case.style,
            'classification': case.classification,
            'file_date': case.file_date.isoformat() if case.file_date else None,
            'case_url': case.case_url,
            'property_address': case.property_address,
            'current_bid_amount': float(case.current_bid_amount) if case.current_bid_amount else None,
            'minimum_next_bid': float(case.minimum_next_bid) if case.minimum_next_bid else None,
            'next_bid_deadline': case.next_bid_deadline.isoformat() if case.next_bid_deadline else None,
            'sale_date': case.sale_date.isoformat() if case.sale_date else None,
            'legal_description': case.legal_description,
            'trustee_name': case.trustee_name,
            'attorney_name': case.attorney_name,
            'attorney_phone': case.attorney_phone,
            'attorney_email': case.attorney_email,
            'our_initial_bid': float(case.our_initial_bid) if case.our_initial_bid else None,
            'our_second_bid': float(case.our_second_bid) if case.our_second_bid else None,
            'our_max_bid': float(case.our_max_bid) if case.our_max_bid else None,
            'team_notes': case.team_notes,
            'parties': parties,
            'events': events,
            'hearings': hearings,
            'upset_bidders': upset_bidders,
            'is_watchlisted': is_watchlisted,
            'photo_url': None
        })
```

### How to Verify

```bash
# 1. Restart Flask API
cd /home/ahn/projects/nc_foreclosures
source venv/bin/activate
export PYTHONPATH=$(pwd)
sudo service postgresql start

# Stop existing Flask process (if running)
pkill -f "web_app.app"

# Start Flask API in background
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(port=5001)" &

# Wait for server to start
sleep 3

# 2. Test PATCH endpoint (replace <case_id> with real ID from DB)
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{
    "our_initial_bid": 50000,
    "our_second_bid": 55000,
    "our_max_bid": 60000,
    "team_notes": "Test note from API"
  }' \
  --cookie "session=<your_session_cookie>"

# Expected: JSON response with updated fields

# 3. Test validation (should fail)
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{
    "our_initial_bid": 60000,
    "our_second_bid": 55000,
    "our_max_bid": 50000
  }' \
  --cookie "session=<your_session_cookie>"

# Expected: {"error": "Invalid bid ladder: our_initial_bid <= our_second_bid <= our_max_bid"}

# 4. Test GET endpoint includes new fields
curl http://localhost:5001/api/cases/1 --cookie "session=<your_session_cookie>"

# Expected: JSON includes our_initial_bid, our_second_bid, our_max_bid, team_notes
```

**Note:** If you get 401 Unauthorized, log in via browser first at http://localhost:5001/login, then extract session cookie from browser dev tools.

---

## Task 3: Frontend API Client Function

**Goal:** Add `updateCase()` function to API client for PATCH requests.

### Files to Modify

**File:** `/home/ahn/projects/nc_foreclosures/frontend/src/api/cases.js`

**What to Add:** Add new function at the end of the file (after line 87).

**Code to Add:**
```javascript
/**
 * Update case collaboration fields
 */
export async function updateCase(caseId, updates) {
  const response = await fetch(`${API_BASE}/cases/${caseId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json'
    },
    credentials: 'include',
    body: JSON.stringify(updates)
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to update case');
  }
  return response.json();
}
```

### How to Verify

```bash
# 1. Check syntax
cd /home/ahn/projects/nc_foreclosures/frontend
npm run build

# Expected: Build succeeds with no errors

# 2. Test in browser console (after npm run dev)
# Open http://localhost:5173, login, navigate to a case detail page
# Open browser console and run:

import { updateCase } from '/src/api/cases.js';
updateCase(1, { team_notes: 'Test from browser' })
  .then(data => console.log('Success:', data))
  .catch(err => console.error('Error:', err));

# Expected: Console shows "Success:" with updated case object
```

---

## Task 4: Frontend Auto-Save Hook

**Goal:** Create reusable `useAutoSave` hook for auto-saving with debounce.

### Files to Create

**File:** `/home/ahn/projects/nc_foreclosures/frontend/src/hooks/useAutoSave.js` (NEW)

**Content:**
```javascript
import { useEffect, useRef, useState } from 'react';

/**
 * Auto-save hook with debounce and state tracking
 *
 * @param {Function} saveFn - Async function to call when saving
 * @param {any} value - Current value to save
 * @param {number} delay - Debounce delay in milliseconds (default 1500)
 * @returns {Object} - { saveState, error }
 *   saveState: 'idle' | 'saving' | 'saved' | 'error'
 *   error: Error message if save failed
 */
export function useAutoSave(saveFn, value, delay = 1500) {
  const [saveState, setSaveState] = useState('idle');
  const [error, setError] = useState(null);
  const timeoutRef = useRef(null);
  const previousValueRef = useRef(value);
  const unmountSaveRef = useRef(false);

  useEffect(() => {
    // Skip if value hasn't changed
    if (value === previousValueRef.current) {
      return;
    }

    previousValueRef.current = value;

    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Set new timeout
    timeoutRef.current = setTimeout(async () => {
      setSaveState('saving');
      setError(null);

      try {
        await saveFn(value);
        setSaveState('saved');

        // Reset to idle after 2 seconds
        setTimeout(() => {
          setSaveState('idle');
        }, 2000);
      } catch (err) {
        setSaveState('error');
        setError(err.message || 'Save failed');
      }
    }, delay);

    // Cleanup
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [value, saveFn, delay]);

  // Save on unmount if dirty
  useEffect(() => {
    return () => {
      if (value !== previousValueRef.current && !unmountSaveRef.current) {
        unmountSaveRef.current = true;
        // Fire-and-forget save
        saveFn(value).catch(err => {
          console.error('Unmount save failed:', err);
        });
      }
    };
  }, [value, saveFn]);

  return { saveState, error };
}
```

### How to Verify

```bash
# 1. Check syntax
cd /home/ahn/projects/nc_foreclosures/frontend
npm run build

# Expected: Build succeeds with no errors

# 2. Create test component to verify hook behavior
# Create frontend/src/hooks/useAutoSave.test.js:

import { renderHook, act, waitFor } from '@testing-library/react';
import { useAutoSave } from './useAutoSave';

test('debounces save calls', async () => {
  const saveFn = jest.fn().mockResolvedValue(true);
  const { result, rerender } = renderHook(
    ({ value }) => useAutoSave(saveFn, value, 100),
    { initialProps: { value: 'initial' } }
  );

  expect(result.current.saveState).toBe('idle');

  // Change value multiple times rapidly
  rerender({ value: 'change1' });
  rerender({ value: 'change2' });
  rerender({ value: 'change3' });

  // Should only call saveFn once after debounce
  await waitFor(() => {
    expect(saveFn).toHaveBeenCalledTimes(1);
    expect(saveFn).toHaveBeenCalledWith('change3');
  });
});

# Run test: npm test -- useAutoSave.test.js
```

**Note:** If you don't have Jest configured, skip the test and verify manually in Task 8.

---

## Task 5: Notes Card Component

**Goal:** Create `NotesCard` component with auto-save textarea.

### Files to Create

**File:** `/home/ahn/projects/nc_foreclosures/frontend/src/components/NotesCard.jsx` (NEW)

**Content:**
```javascript
import { useState, useCallback } from 'react';
import { Card, Input, Typography, Space } from 'antd';
import { CheckCircleOutlined, LoadingOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useAutoSave } from '../hooks/useAutoSave';

const { TextArea } = Input;
const { Text } = Typography;

/**
 * NotesCard - Auto-saving team notes for a case
 *
 * @param {string} initialNotes - Initial notes value from API
 * @param {Function} onSave - Async function to save notes (receives notes string)
 */
function NotesCard({ initialNotes, onSave }) {
  const [notes, setNotes] = useState(initialNotes || '');

  // Memoize save function to prevent re-renders
  const handleSave = useCallback(async (value) => {
    await onSave({ team_notes: value });
  }, [onSave]);

  const { saveState, error } = useAutoSave(handleSave, notes);

  return (
    <Card
      title="Team Notes"
      extra={
        <Space size={4}>
          {saveState === 'saving' && (
            <>
              <LoadingOutlined style={{ color: '#1890ff' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>Saving...</Text>
            </>
          )}
          {saveState === 'saved' && (
            <>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              <Text type="success" style={{ fontSize: 12 }}>Saved</Text>
            </>
          )}
          {saveState === 'error' && (
            <>
              <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
              <Text type="danger" style={{ fontSize: 12 }}>Save failed</Text>
            </>
          )}
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <TextArea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Add notes about property condition, research findings, strategy..."
        autoSize={{ minRows: 4, maxRows: 20 }}
        style={{ fontSize: 14 }}
      />
      {error && (
        <Text type="danger" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          {error}
        </Text>
      )}
    </Card>
  );
}

export default NotesCard;
```

### How to Verify

```bash
# 1. Check syntax
cd /home/ahn/projects/nc_foreclosures/frontend
npm run build

# Expected: Build succeeds with no errors

# 2. Create standalone test page (optional)
# Create frontend/src/pages/NotesCardTest.jsx:

import { useState } from 'react';
import NotesCard from '../components/NotesCard';

function NotesCardTest() {
  const [savedValue, setSavedValue] = useState('');

  const handleSave = async (updates) => {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500));
    setSavedValue(updates.team_notes);
    console.log('Saved:', updates.team_notes);
  };

  return (
    <div style={{ padding: 24, maxWidth: 600 }}>
      <NotesCard initialNotes="Initial test notes" onSave={handleSave} />
      <div style={{ marginTop: 16 }}>
        <strong>Last saved value:</strong> {savedValue}
      </div>
    </div>
  );
}

export default NotesCardTest;

# 3. Add route to App.jsx and test in browser
# Should see auto-save indicator when typing stops
```

---

## Task 6: Bid Ladder Editable Inputs

**Goal:** Add editable bid inputs to Bid Information Card with validation and auto-save.

### Files to Modify

**File:** `/home/ahn/projects/nc_foreclosures/frontend/src/pages/CaseDetail.jsx`

**What to Add:** Import statements at the top (after existing imports):

```javascript
import { InputNumber } from 'antd';
import { useAutoSave } from '../hooks/useAutoSave';
import { updateCase } from '../api/cases';
```

**What to Add:** State variables after line 29 (after `const [error, setError] = useState(null);`):

```javascript
  // Bid ladder state
  const [ourInitialBid, setOurInitialBid] = useState(null);
  const [ourSecondBid, setOurSecondBid] = useState(null);
  const [ourMaxBid, setOurMaxBid] = useState(null);
  const [bidValidationError, setBidValidationError] = useState(null);
```

**What to Modify:** Update `loadCase` function (lines 32-43) to initialize bid state:

**Find this code:**
```javascript
  useEffect(() => {
    async function loadCase() {
      try {
        setLoading(true);
        const data = await fetchCase(id);
        setCaseData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadCase();
  }, [id]);
```

**Replace with:**
```javascript
  useEffect(() => {
    async function loadCase() {
      try {
        setLoading(true);
        const data = await fetchCase(id);
        setCaseData(data);

        // Initialize bid ladder state
        setOurInitialBid(data.our_initial_bid);
        setOurSecondBid(data.our_second_bid);
        setOurMaxBid(data.our_max_bid);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadCase();
  }, [id]);
```

**What to Add:** Bid save handler after `handleWatchlistToggle` function (after line 61):

```javascript
  // Auto-save bid ladder
  const handleBidSave = useCallback(async (updates) => {
    try {
      // Validate bid ladder
      const initial = updates.our_initial_bid ?? ourInitialBid;
      const second = updates.our_second_bid ?? ourSecondBid;
      const max = updates.our_max_bid ?? ourMaxBid;

      if (initial !== null && second !== null && max !== null) {
        if (initial > second || second > max) {
          setBidValidationError('Bids must be: Initial ≤ 2nd ≤ Max');
          return;
        }
      }

      setBidValidationError(null);
      const updatedCase = await updateCase(id, updates);
      setCaseData(updatedCase);
    } catch (err) {
      message.error('Failed to save bid ladder');
      throw err;
    }
  }, [id, ourInitialBid, ourSecondBid, ourMaxBid]);

  // Auto-save hooks for each bid field
  const { saveState: initialBidSaveState } = useAutoSave(
    (value) => handleBidSave({ our_initial_bid: value }),
    ourInitialBid
  );
  const { saveState: secondBidSaveState } = useAutoSave(
    (value) => handleBidSave({ our_second_bid: value }),
    ourSecondBid
  );
  const { saveState: maxBidSaveState } = useAutoSave(
    (value) => handleBidSave({ our_max_bid: value }),
    ourMaxBid
  );

  // Unified save state for the card (show if any field is saving/saved)
  const bidCardSaveState = initialBidSaveState === 'saving' ||
                           secondBidSaveState === 'saving' ||
                           maxBidSaveState === 'saving'
                           ? 'saving'
                           : initialBidSaveState === 'saved' ||
                             secondBidSaveState === 'saved' ||
                             maxBidSaveState === 'saved'
                           ? 'saved'
                           : 'idle';
```

**What to Replace:** Replace the "Bid Ladder Display" section (lines 244-262).

**Find this code:**
```javascript
            {/* Bid Ladder Display */}
            <Title level={5}>Your Bid Ladder</Title>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="Initial Bid">
                <Text type="secondary">Not set</Text>
              </Descriptions.Item>
              <Descriptions.Item label="2nd Bid">
                <Text type="secondary">Not set</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Max Bid">
                <Text type="secondary">Not set</Text>
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Bid ladder editing coming in Phase 3
              </Text>
            </div>
```

**Replace with:**
```javascript
            {/* Bid Ladder Editable */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Title level={5} style={{ margin: 0 }}>Your Bid Ladder</Title>
              <Space size={4}>
                {bidCardSaveState === 'saving' && (
                  <>
                    <LoadingOutlined style={{ color: '#1890ff', fontSize: 12 }} />
                    <Text type="secondary" style={{ fontSize: 12 }}>Saving...</Text>
                  </>
                )}
                {bidCardSaveState === 'saved' && (
                  <>
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 12 }} />
                    <Text type="success" style={{ fontSize: 12 }}>Saved</Text>
                  </>
                )}
              </Space>
            </div>

            <div style={{ marginTop: 12 }}>
              <Space direction="vertical" style={{ width: '100%' }} size="small">
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Our Initial Bid</Text>
                  <InputNumber
                    value={ourInitialBid}
                    onChange={setOurInitialBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%', marginTop: 4 }}
                    min={0}
                    step={100}
                    placeholder="Enter initial bid"
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Our 2nd Bid</Text>
                  <InputNumber
                    value={ourSecondBid}
                    onChange={setOurSecondBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%', marginTop: 4 }}
                    min={0}
                    step={100}
                    placeholder="Enter 2nd bid"
                  />
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>Our Max Bid</Text>
                  <InputNumber
                    value={ourMaxBid}
                    onChange={setOurMaxBid}
                    formatter={value => `$${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
                    parser={value => value.replace(/\$\s?|(,*)/g, '')}
                    style={{ width: '100%', marginTop: 4 }}
                    min={0}
                    step={100}
                    placeholder="Enter max bid"
                  />
                </div>
              </Space>

              {bidValidationError && (
                <Alert
                  type="error"
                  message={bidValidationError}
                  showIcon
                  style={{ marginTop: 12 }}
                />
              )}
            </div>
```

**What to Add:** Import `useCallback` at the top (modify existing import):

**Find:** `import { useState, useEffect } from 'react';`
**Replace with:** `import { useState, useEffect, useCallback } from 'react';`

**What to Add:** Import icons at the top (modify existing icon imports):

**Find:**
```javascript
import {
  ArrowLeftOutlined, StarOutlined, StarFilled,
  LinkOutlined, FileTextOutlined, PictureOutlined
} from '@ant-design/icons';
```

**Replace with:**
```javascript
import {
  ArrowLeftOutlined, StarOutlined, StarFilled,
  LinkOutlined, FileTextOutlined, PictureOutlined,
  LoadingOutlined, CheckCircleOutlined
} from '@ant-design/icons';
```

### How to Verify

```bash
# 1. Check syntax
cd /home/ahn/projects/nc_foreclosures/frontend
npm run build

# Expected: Build succeeds with no errors

# 2. Start dev server
npm run dev -- --host

# 3. Test in browser
# - Navigate to http://localhost:5173
# - Login with Google
# - Open any case detail page
# - Scroll to "Bid Information" card
# - Enter values in bid ladder inputs
# - Verify "Saving..." indicator appears after 1.5s
# - Verify "Saved" indicator appears after save completes
# - Verify values persist on page reload
# - Test validation: Enter Max < Initial, verify error message

# 4. Test API persistence
curl http://localhost:5001/api/cases/1 --cookie "session=<your_cookie>"
# Verify our_initial_bid, our_second_bid, our_max_bid fields have saved values
```

---

## Task 7: Case Detail Page Layout Reorganization

**Goal:** Move Bid Information card from right column to left column, add Notes Card to right column.

### Files to Modify

**File:** `/home/ahn/projects/nc_foreclosures/frontend/src/pages/CaseDetail.jsx`

**What to Add:** Import NotesCard component at the top:

```javascript
import NotesCard from '../components/NotesCard';
```

**What to Add:** Team notes state and save handler after bid state (around line 33):

```javascript
  // Team notes state
  const [teamNotes, setTeamNotes] = useState('');
```

**What to Modify:** Update `loadCase` function to initialize team notes:

**Find the section where you set bid state (from Task 6):**
```javascript
        // Initialize bid ladder state
        setOurInitialBid(data.our_initial_bid);
        setOurSecondBid(data.our_second_bid);
        setOurMaxBid(data.our_max_bid);
```

**Add below it:**
```javascript
        // Initialize team notes
        setTeamNotes(data.team_notes || '');
```

**What to Add:** Notes save handler (after bid save handlers):

```javascript
  // Auto-save team notes
  const handleNotesSave = useCallback(async (updates) => {
    try {
      const updatedCase = await updateCase(id, updates);
      setCaseData(updatedCase);
    } catch (err) {
      message.error('Failed to save notes');
      throw err;
    }
  }, [id]);
```

**What to Move:** Move the entire "Bid Information" Card from right column (lines 224-263) to left column after the "Property" Card.

**Current structure:**
```
<Row gutter={16}>
  {/* Left Column */}
  <Col xs={24} lg={12}>
    <Card title="Property">...</Card>
    <Card title="Parties">...</Card>
    <Card title="Upset Bidders">...</Card>  <!-- if exists -->
  </Col>

  {/* Right Column */}
  <Col xs={24} lg={12}>
    <Card title="Bid Information">...</Card>  <!-- MOVE THIS -->
    <Card title="Contacts">...</Card>
    <Card title="Events Timeline">...</Card>
  </Col>
</Row>
```

**New structure:**
```
<Row gutter={16}>
  {/* Left Column */}
  <Col xs={24} lg={12}>
    <Card title="Property">...</Card>
    <Card title="Bid Information">...</Card>  <!-- MOVED HERE -->
    <Card title="Parties">...</Card>
    <Card title="Upset Bidders">...</Card>  <!-- if exists -->
  </Col>

  {/* Right Column */}
  <Col xs={24} lg={12}>
    <NotesCard initialNotes={teamNotes} onSave={handleNotesSave} />  <!-- NEW -->
    <Card title="Contacts">...</Card>
    <Card title="Events Timeline">...</Card>
  </Col>
</Row>
```

**Exact code to add in right column (after opening `<Col xs={24} lg={12}>` tag):**

```javascript
          {/* Team Notes */}
          <NotesCard
            initialNotes={teamNotes}
            onSave={handleNotesSave}
          />
```

### How to Verify

```bash
# 1. Check syntax
cd /home/ahn/projects/nc_foreclosures/frontend
npm run build

# Expected: Build succeeds

# 2. Visual verification in browser
# Navigate to case detail page
# Verify layout:
#   LEFT column (top to bottom):
#     - Property Card
#     - Bid Information Card (with editable inputs)
#     - Parties Card
#     - Upset Bidders Card (if any)
#   RIGHT column (top to bottom):
#     - Team Notes Card (new)
#     - Contacts Card
#     - Events Timeline Card

# 3. Test notes auto-save
# - Type in notes textarea
# - Stop typing for 1.5s
# - Verify "Saving..." then "Saved" indicator
# - Reload page
# - Verify notes persisted
```

---

## Task 8: Integration and Testing

**Goal:** End-to-end testing of all collaboration features.

### Testing Checklist

#### Setup

```bash
# 1. Start PostgreSQL
sudo service postgresql start

# 2. Start Flask API
cd /home/ahn/projects/nc_foreclosures
source venv/bin/activate
export PYTHONPATH=$(pwd)
pkill -f "web_app.app"
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(port=5001)" &

# 3. Start frontend dev server
cd frontend
pkill -f "vite"
npm run dev -- --host &

# Wait for servers to start
sleep 5

# 4. Open browser to http://localhost:5173
```

#### Test Scenarios

**Test 1: Basic Save**
1. Login and navigate to any upset_bid case
2. Enter bid values:
   - Initial: $50,000
   - 2nd: $55,000
   - Max: $60,000
3. Wait 1.5 seconds
4. Verify "Saving..." indicator appears
5. Verify "Saved" indicator appears after ~1s
6. Reload page
7. Verify values persisted

**Test 2: Notes Auto-Save**
1. Type in notes textarea: "Property needs roof work. Budget $15k for repairs."
2. Wait 1.5 seconds
3. Verify "Saving..." then "Saved" indicator
4. Reload page
5. Verify notes persisted

**Test 3: Rapid Edits**
1. Type rapidly in notes for 5 seconds without stopping
2. Stop typing
3. Verify only ONE "Saving..." indicator (debounce working)
4. Verify final text saved correctly

**Test 4: Navigation During Edit**
1. Type in notes textarea
2. Immediately click "Back to Cases" (before 1.5s debounce)
3. Navigate back to case detail
4. Verify notes were saved on unmount

**Test 5: Validation**
1. Enter bids:
   - Initial: $60,000
   - 2nd: $55,000
   - Max: $50,000
2. Verify error alert appears: "Bids must be: Initial ≤ 2nd ≤ Max"
3. Fix to valid order
4. Verify error clears and save succeeds

**Test 6: Error Recovery**
1. Stop Flask API: `pkill -f "web_app.app"`
2. Edit notes in browser
3. Wait 1.5 seconds
4. Verify "Save failed" message
5. Restart Flask API
6. Edit notes again
7. Verify save succeeds (retry on next edit)

**Test 7: Concurrent Users** (requires 2 browsers)
1. Open case in Chrome (User A)
2. Open same case in Firefox (User B)
3. User A sets initial bid to $50,000
4. User B sets initial bid to $55,000 (after User A's save completes)
5. Reload both browsers
6. Verify both see $55,000 (last write wins)

**Test 8: Empty Values**
1. Set all bid fields to values
2. Clear all fields (delete numbers)
3. Wait for save
4. Reload page
5. Verify fields are empty (nulls saved correctly)

**Test 9: Currency Format**
1. Enter "50000" in initial bid
2. Click outside field
3. Verify displays as "$50,000"
4. Click into field
5. Verify shows "50000" (no formatting when editing)

#### API Testing

```bash
# Test PATCH endpoint directly
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{
    "our_initial_bid": 75000,
    "team_notes": "API test note"
  }' \
  --cookie "session=<cookie>"

# Verify response includes updated fields

# Test validation
curl -X PATCH http://localhost:5001/api/cases/1 \
  -H "Content-Type: application/json" \
  -d '{
    "our_initial_bid": 60000,
    "our_second_bid": 50000,
    "our_max_bid": 40000
  }' \
  --cookie "session=<cookie>"

# Expected 400 error with validation message
```

#### Database Verification

```bash
# Check data in database
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT
  case_number,
  our_initial_bid,
  our_second_bid,
  our_max_bid,
  LEFT(team_notes, 50) as team_notes_preview
FROM cases
WHERE our_initial_bid IS NOT NULL
   OR our_second_bid IS NOT NULL
   OR our_max_bid IS NOT NULL
   OR team_notes IS NOT NULL
LIMIT 10;
"

# Expected: Shows cases with collaboration data
```

#### Performance Testing

```bash
# Test auto-save doesn't block UI
# 1. Open case detail page
# 2. Open browser performance tools (F12 > Performance tab)
# 3. Start recording
# 4. Type in notes for 5 seconds
# 5. Stop recording
# 6. Verify no long tasks > 50ms (UI should remain responsive)

# Test network requests
# 1. Open Network tab
# 2. Type in notes
# 3. Wait for save
# 4. Verify PATCH request to /api/cases/<id>
# 5. Verify request payload contains only changed field
# 6. Verify response is full case object
```

### Success Criteria

- ✅ All 9 test scenarios pass
- ✅ Auto-save latency < 2 seconds
- ✅ Zero data loss on navigation
- ✅ Bid validation prevents invalid data
- ✅ UI responsive during save (no blocking)
- ✅ Database shows correct data
- ✅ API returns proper error messages
- ✅ Currency formatting works correctly

### Rollback Plan

If critical issues found:

```bash
# 1. Revert frontend changes
cd /home/ahn/projects/nc_foreclosures/frontend
git checkout HEAD -- src/pages/CaseDetail.jsx src/components/NotesCard.jsx src/hooks/useAutoSave.js src/api/cases.js

# 2. Revert backend changes
cd /home/ahn/projects/nc_foreclosures
git checkout HEAD -- web_app/api/cases.py database/models.py

# 3. Rollback database migration
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
ALTER TABLE cases DROP COLUMN IF EXISTS our_initial_bid;
ALTER TABLE cases DROP COLUMN IF EXISTS our_second_bid;
ALTER TABLE cases DROP COLUMN IF EXISTS our_max_bid;
ALTER TABLE cases DROP COLUMN IF EXISTS team_notes;
"

# 4. Restart services
pkill -f "web_app.app"
pkill -f "vite"
# Restart normally
```

---

## Summary

This implementation adds team collaboration features to the NC Foreclosures case detail page:

**Database:**
- 4 new columns on `cases` table (no new tables)

**Backend:**
- `PATCH /api/cases/<id>` endpoint with validation
- Bid ladder validation (initial ≤ 2nd ≤ max)

**Frontend:**
- `useAutoSave` hook (1.5s debounce, save on unmount)
- `NotesCard` component with auto-save
- Editable bid ladder with currency formatting
- Reorganized layout (bid info moved to left column)

**Key Features:**
- Auto-save everything (no save button required)
- Save indicators (Saving... → Saved ✓)
- Client-side validation before save
- Last write wins for concurrent edits
- Fire-and-forget save on navigation

**Total Files Changed:** 8
- 1 migration SQL
- 2 backend files (models, API)
- 5 frontend files (hook, component, API client, page)

Each task is independent and can be executed by a subagent with zero codebase context.
