# Phase 3: Collaboration Features Design

**Date:** December 13, 2025
**Status:** Design
**Scope:** Add team collaboration features to Case Detail page

## Overview

Add shared notes and bid ladder editing to enable team collaboration on upset bid opportunities. All features are shared across the team - no per-user data.

## Goals

1. Allow team to track internal bid strategy per case
2. Enable shared note-taking for property observations and decisions
3. Auto-save changes to minimize friction
4. Keep UI simple - no edit history or complex permissions

## Data Model

### Database Changes

Add 4 columns to existing `cases` table:

```sql
ALTER TABLE cases ADD COLUMN our_initial_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN our_second_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN our_max_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN team_notes TEXT;
```

**No new tables needed.** All collaboration data lives on the case record.

### Field Descriptions

| Field | Type | Purpose |
|-------|------|---------|
| `our_initial_bid` | DECIMAL(12,2) | Our planned first upset bid amount |
| `our_second_bid` | DECIMAL(12,2) | Our planned second upset bid if outbid |
| `our_max_bid` | DECIMAL(12,2) | Maximum amount we're willing to bid |
| `team_notes` | TEXT | Shared notes about property, strategy, research |

## API Design

### PATCH /api/cases/\<id\>

Update case collaboration fields.

**Request Body:**
```json
{
  "our_initial_bid": 50000,
  "our_second_bid": 55000,
  "our_max_bid": 60000,
  "team_notes": "Property looks good. Needs roof work (~15k)."
}
```

**Response:**
```json
{
  "id": "25SP000123-910",
  "classification": "upset_bid",
  "our_initial_bid": 50000.00,
  "our_second_bid": 55000.00,
  "our_max_bid": 60000.00,
  "team_notes": "Property looks good. Needs roof work (~15k).",
  ...
}
```

**Rules:**
- All fields optional - send only what changed
- Returns full updated case object
- Validation: `our_initial_bid <= our_second_bid <= our_max_bid`
- 404 if case doesn't exist
- 403 if user not authenticated

**Existing Endpoint:**
- `GET /api/cases/<id>` automatically returns new fields (no changes needed)

## Frontend Design

### Layout Changes

**Left Column (top to bottom):**
1. Property Card (unchanged)
2. **Bid Information Card** (moved from right column)
   - Current Bid (readonly)
   - Minimum Next Bid (readonly)
   - Sale Date (readonly)
   - Upset Deadline (readonly)
   - **Our Initial Bid** (editable)
   - **Our 2nd Bid** (editable)
   - **Our Max Bid** (editable)
3. Parties Card (unchanged)
4. Upset Bidders Card (unchanged)

**Right Column (top to bottom):**
1. **Notes Card** (NEW)
   - Title: "Team Notes"
   - Single textarea (auto-expanding)
   - Save indicator
2. Contacts Card (unchanged)
3. Events Timeline Card (unchanged)

### Notes Card

**UI Elements:**
- Card header: "Team Notes"
- Full-width textarea (min 100px height, auto-expand)
- Save indicator in top-right: "Saving..." / "Saved ✓" / "Save failed"
- Placeholder: "Add notes about property condition, research findings, strategy..."

**Behavior:**
- Auto-save on blur or after 1.5s debounce
- Show "Saving..." during API call
- Show "Saved ✓" for 2s after success
- Show "Save failed" in red on error, retry on next edit

### Bid Ladder UI

**UI Elements:**
- Three `InputNumber` fields with labels:
  - "Our Initial Bid"
  - "Our 2nd Bid"
  - "Our Max Bid"
- Currency formatter: `$50,000` display, number input when focused
- Min value: 0
- Step: 100

**Behavior:**
- Same auto-save logic as notes
- All 3 fields share single save indicator for the card
- Client-side validation: Initial ≤ 2nd ≤ Max (disable save if violated)

## Auto-Save Implementation

### Debounce Logic

```javascript
// Pseudo-code
const [saveState, setSaveState] = useState('idle'); // idle | saving | saved | error

useEffect(() => {
  if (!isDirty) return;

  const timer = setTimeout(async () => {
    setSaveState('saving');
    try {
      await updateCase(caseId, changedFields);
      setSaveState('saved');
      setTimeout(() => setSaveState('idle'), 2000);
    } catch (error) {
      setSaveState('error');
    }
  }, 1500);

  return () => clearTimeout(timer);
}, [notes, ourInitialBid, ourSecondBid, ourMaxBid]);
```

### Save on Unmount

```javascript
useEffect(() => {
  return () => {
    if (isDirty) {
      // Fire-and-forget save before unmounting
      updateCase(caseId, changedFields);
    }
  };
}, [isDirty]);
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User types rapidly | Debounce resets, only final state saved |
| Navigate away while typing | Save immediately on unmount |
| API error | Show "Save failed", retry on next edit |
| Concurrent edits (2 users) | Last write wins (no conflict resolution) |
| Network offline | Failed save message, retry when online |

## Implementation Checklist

### Backend
- [ ] Create migration: `migrations/add_collaboration_fields.sql`
- [ ] Add fields to `Case` SQLAlchemy model
- [ ] Create `PATCH /api/cases/<id>` endpoint
- [ ] Add validation: `our_initial_bid <= our_second_bid <= our_max_bid`
- [ ] Return new fields in existing `GET /api/cases/<id>`

### Frontend
- [ ] Rearrange cards: move Bid Information to left column
- [ ] Create `NotesCard` component
- [ ] Add bid ladder inputs to `BidInformationCard`
- [ ] Create `useAutoSave` hook
- [ ] Add save indicator component
- [ ] Add client-side bid validation
- [ ] Handle save on unmount

## Future Enhancements (Out of Scope)

- Edit history / audit log
- Per-user notes
- Real-time collaboration (multiple users editing)
- Notifications when notes change
- @mentions in notes
- Rich text formatting

## Migration File

```sql
-- migrations/add_collaboration_fields.sql
ALTER TABLE cases ADD COLUMN our_initial_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN our_second_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN our_max_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN team_notes TEXT;
```

## Testing Scenarios

1. **Basic Save:** Edit notes, wait 1.5s, verify API call
2. **Rapid Edits:** Type quickly, verify only one API call
3. **Navigation:** Edit notes, click away, verify save on unmount
4. **Validation:** Enter Max < Initial, verify error message
5. **Error Recovery:** Simulate API error, verify retry on next edit
6. **Concurrent Users:** Two users edit same case, verify last write wins
7. **Empty Values:** Clear all fields, verify nulls saved correctly
8. **Currency Format:** Enter 50000, verify displays as $50,000

## Success Metrics

- Auto-save latency < 2s
- Zero data loss on navigation
- Bid validation prevents invalid data
- UI responsive during save (no blocking)
