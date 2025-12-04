# Classification Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable detection of non-foreclosure sales (ward's estate, tax liens, etc.) with human-in-the-loop review queue.

**Architecture:** Add document title pattern matching to scraper detection, log all skipped cases to new database table, expose review API endpoints, add Review Queue page to React frontend with bulk actions.

**Tech Stack:** Python/SQLAlchemy (backend), Flask (API), React/Ant Design (frontend), PostgreSQL (database)

---

## Task 1: Add skipped_cases Table to Database

**Files:**
- Modify: `database/schema.sql`
- Modify: `database/models.py`

**Step 1: Add table to schema.sql**

Add after the `user_notes` table (around line 97):

```sql
-- Skipped cases table - Cases examined but not saved during daily scrape
CREATE TABLE IF NOT EXISTS skipped_cases (
    id SERIAL PRIMARY KEY,
    case_number VARCHAR(50) NOT NULL,
    county_code VARCHAR(10) NOT NULL,
    county_name VARCHAR(50) NOT NULL,
    case_url TEXT,
    case_type VARCHAR(100),
    style TEXT,
    file_date DATE,
    events_json JSONB,
    skip_reason VARCHAR(255),
    scrape_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    review_action VARCHAR(20)
);

CREATE INDEX IF NOT EXISTS idx_skipped_cases_scrape_date ON skipped_cases(scrape_date);
CREATE INDEX IF NOT EXISTS idx_skipped_cases_reviewed ON skipped_cases(reviewed_at);
```

**Step 2: Add SkippedCase model to models.py**

Add after the `SchedulerConfig` class (around line 189):

```python
class SkippedCase(Base):
    """Cases examined but not saved during daily scrape - for review."""

    __tablename__ = 'skipped_cases'

    id = Column(Integer, primary_key=True)
    case_number = Column(String(50), nullable=False)
    county_code = Column(String(10), nullable=False)
    county_name = Column(String(50), nullable=False)
    case_url = Column(Text)
    case_type = Column(String(100))
    style = Column(Text)
    file_date = Column(Date)
    events_json = Column(Text)  # JSON string of events with document titles
    skip_reason = Column(String(255))
    scrape_date = Column(Date, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    reviewed_at = Column(TIMESTAMP)
    review_action = Column(String(20))  # 'added', 'dismissed', NULL (pending)

    def __repr__(self):
        return f"<SkippedCase(case_number='{self.case_number}', scrape_date='{self.scrape_date}')>"
```

**Step 3: Run migration to create table**

```bash
cd /home/ahn/projects/nc_foreclosures
source venv/bin/activate
export PYTHONPATH=$(pwd)
sudo service postgresql start

# Run the CREATE TABLE statement
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f database/schema.sql
```

**Step 4: Verify table exists**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d skipped_cases"
```

Expected: Table structure with all columns shown.

**Step 5: Commit**

```bash
git add database/schema.sql database/models.py
git commit -m "feat: add skipped_cases table for review queue

Stores cases examined during daily scrape that didn't match
foreclosure indicators, allowing manual review and override."
```

---

## Task 2: Add Document Title Detection Indicators

**Files:**
- Modify: `scraper/page_parser.py`

**Step 1: Add SALE_DOCUMENT_INDICATORS list**

Add after `UPSET_BID_OPPORTUNITY_INDICATORS` (around line 28):

```python
# Document title patterns that indicate a potential sale with upset bid rights
# These are checked against document titles (not event types) for day-1 detection
SALE_DOCUMENT_INDICATORS = [
    'petition to sell',
    'petition to lease',
    'petition to mortgage',
    "ward's estate",
    "incompetent's estate",
    "minor's estate",
    "decedent's estate",
    'sell real property',
    'tax lien foreclosure',
    'tax foreclosure',
    'delinquent tax',
    'receivership',
    "receiver's sale",
    'trust property sale',
    'sell trust property',
]
```

**Step 2: Modify parse_case_detail to capture document titles**

In the `parse_case_detail` function, update the events parsing section (around line 260-310) to also capture document titles. Find the section that extracts event_type and add document_title extraction:

After line 280 (after extracting event_type), add:

```python
        # Extract document title (text on clickable document link)
        document_title = None
        doc_link = event_div.find('a') or event_div.find('button', attrs={'aria-label': lambda v: v and 'document' in v.lower()})
        if doc_link:
            # Get text near the document link - usually the document title
            doc_text = doc_link.get_text(strip=True) if doc_link else None
            if not doc_text or doc_text == 'Click here to view the document':
                # Look for text in sibling or parent elements
                parent = doc_link.parent
                if parent:
                    # Get all text in the parent, excluding common labels
                    parent_text = parent.get_text(' ', strip=True)
                    # Extract document title - usually after "A document is available"
                    for line in parent_text.split('\n'):
                        line = line.strip()
                        if line and 'document is available' not in line.lower() and 'click here' not in line.lower():
                            if 5 < len(line) < 200 and not line.startswith('Index') and not line.startswith('Created'):
                                document_title = line
                                break
            else:
                document_title = doc_text
```

Then update the event_data dict (around line 297-308) to include document_title:

```python
        if event_date or event_type:
            event_data = {
                'event_date': event_date,
                'event_type': event_type,
                'event_description': None,
                'document_title': document_title,  # NEW: Add document title
                'filed_by': filed_by_match.group(1).strip() if filed_by_match else None,
                'filed_against': against_match.group(1).strip() if against_match else None,
                'hearing_date': f"{hearing_match.group(1)} {hearing_match.group(2)}" if hearing_match else None,
                'document_url': None,
                'has_document': has_document
            }
            case_data['events'].append(event_data)
            logger.debug(f"Event: {event_date} - {event_type} - Doc: {document_title}")
```

**Step 3: Modify is_foreclosure_case to check document titles**

Update the `is_foreclosure_case` function (around line 31-70) to also check document titles:

Add after line 68 (after checking UPSET_BID_OPPORTUNITY_INDICATORS), before `return False`:

```python
    # Check document titles for sale indicators (for day-1 detection)
    for event in events:
        document_title = (event.get('document_title') or '').lower()
        if document_title:
            for indicator in SALE_DOCUMENT_INDICATORS:
                if indicator in document_title:
                    logger.debug(f"Sale opportunity identified by document title: {document_title}")
                    return True
```

**Step 4: Commit**

```bash
git add scraper/page_parser.py
git commit -m "feat: add document title detection for non-foreclosure sales

- Add SALE_DOCUMENT_INDICATORS for ward's estate, tax liens, etc.
- Extract document titles from case events
- Check document titles in is_foreclosure_case()"
```

---

## Task 3: Modify Scraper to Log Skipped Cases

**Files:**
- Modify: `scraper/date_range_scrape.py`

**Step 1: Import SkippedCase model**

Add to imports at top (around line 17):

```python
from database.models import Case, CaseEvent, Party, Hearing, ScrapeLog, SkippedCase
```

Also add json import:

```python
import json
```

**Step 2: Add _save_skipped_case method**

Add after the `_save_case` method (around line 365):

```python
    def _save_skipped_case(self, case_number, case_url, county_code, county_name, case_data, skip_reason):
        """Save a skipped case for later review."""
        with get_session() as session:
            # Check if already saved (avoid duplicates)
            existing = session.query(SkippedCase).filter_by(
                case_number=case_number,
                scrape_date=self.start_date
            ).first()

            if existing:
                logger.debug(f"  Skipped case {case_number} already logged for {self.start_date}")
                return

            # Serialize events with document titles for review
            events_for_review = []
            for event in case_data.get('events', []):
                events_for_review.append({
                    'event_date': event.get('event_date'),
                    'event_type': event.get('event_type'),
                    'document_title': event.get('document_title'),
                    'has_document': event.get('has_document', False)
                })

            skipped = SkippedCase(
                case_number=case_number,
                county_code=county_code,
                county_name=county_name.title(),
                case_url=case_url,
                case_type=case_data.get('case_type'),
                style=case_data.get('style'),
                file_date=case_data.get('file_date'),
                events_json=json.dumps(events_for_review),
                skip_reason=skip_reason,
                scrape_date=self.start_date
            )
            session.add(skipped)
            session.commit()
            logger.info(f"  📋 Logged skipped case {case_number} for review")
```

**Step 3: Modify _process_case_in_new_tab to log skipped cases**

In the `_process_case_in_new_tab` method (around line 220-296), find the section that checks `is_foreclosure_case` (around line 276):

Replace:
```python
            # Check if this is a foreclosure case
            if not is_foreclosure_case(case_data):
                logger.debug(f"  {case_number} is not a foreclosure case, skipping")
                return False
```

With:
```python
            # Check if this is a foreclosure case
            if not is_foreclosure_case(case_data):
                # Log skipped case for review
                self._save_skipped_case(
                    case_number, case_url, county_code, county_name,
                    case_data, "No foreclosure or sale indicators detected"
                )
                return False
```

**Step 4: Commit**

```bash
git add scraper/date_range_scrape.py
git commit -m "feat: log skipped cases during daily scrape for review

Skipped cases are now saved to skipped_cases table with:
- Case details (number, county, type, style)
- Events with document titles (as JSON)
- Skip reason for context"
```

---

## Task 4: Create Review API Endpoints

**Files:**
- Create: `web_app/api/review.py`
- Modify: `web_app/app.py` (in frontend worktree)

**Step 1: Create review.py API blueprint**

Create `/home/ahn/projects/nc_foreclosures/.worktrees/frontend/web_app/api/review.py`:

```python
"""Review Queue API endpoints."""

import json
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify
from sqlalchemy import func

from database.connection import get_session
from database.models import Case, CaseEvent, Party, Hearing, SkippedCase
from scraper.page_parser import parse_case_detail
from common.logger import setup_logger

logger = setup_logger(__name__)

review_bp = Blueprint('review', __name__)


@review_bp.route('/daily', methods=['GET'])
def get_daily_review():
    """
    Get cases for daily review.

    Query params:
        date: YYYY-MM-DD (default: today)

    Returns:
        {
            "date": "2025-12-04",
            "foreclosures": [...],
            "skipped": [...],
            "counts": {"foreclosures": N, "skipped": M}
        }
    """
    date_str = request.args.get('date')

    if date_str:
        try:
            review_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    else:
        review_date = date.today()

    with get_session() as session:
        # Get foreclosures added on this date
        foreclosures = session.query(Case).filter(
            func.date(Case.created_at) == review_date
        ).all()

        foreclosure_list = []
        for case in foreclosures:
            # Get events for this case
            events = session.query(CaseEvent).filter_by(case_id=case.id).all()
            event_list = [
                {
                    'event_date': e.event_date.strftime('%Y-%m-%d') if e.event_date else None,
                    'event_type': e.event_type,
                    'document_url': e.document_url
                }
                for e in events
            ]

            foreclosure_list.append({
                'id': case.id,
                'case_number': case.case_number,
                'county_name': case.county_name,
                'case_type': case.case_type,
                'style': case.style,
                'file_date': case.file_date.strftime('%Y-%m-%d') if case.file_date else None,
                'case_url': case.case_url,
                'classification': case.classification,
                'events': event_list
            })

        # Get skipped cases for this date
        skipped = session.query(SkippedCase).filter(
            SkippedCase.scrape_date == review_date,
            SkippedCase.review_action.is_(None)  # Only pending review
        ).all()

        skipped_list = []
        for case in skipped:
            events = json.loads(case.events_json) if case.events_json else []
            skipped_list.append({
                'id': case.id,
                'case_number': case.case_number,
                'county_name': case.county_name,
                'case_type': case.case_type,
                'style': case.style,
                'file_date': case.file_date.strftime('%Y-%m-%d') if case.file_date else None,
                'case_url': case.case_url,
                'skip_reason': case.skip_reason,
                'events': events
            })

        return jsonify({
            'date': review_date.strftime('%Y-%m-%d'),
            'foreclosures': foreclosure_list,
            'skipped': skipped_list,
            'counts': {
                'foreclosures': len(foreclosure_list),
                'skipped': len(skipped_list),
                'pending_review': len(foreclosure_list) + len(skipped_list)
            }
        })


@review_bp.route('/foreclosures/reject', methods=['POST'])
def reject_foreclosures():
    """
    Reject (delete) foreclosure cases.

    Body:
        {"case_ids": [1, 2, 3]}
    """
    data = request.get_json()
    case_ids = data.get('case_ids', [])

    if not case_ids:
        return jsonify({'error': 'No case_ids provided'}), 400

    with get_session() as session:
        deleted = 0
        for case_id in case_ids:
            case = session.query(Case).filter_by(id=case_id).first()
            if case:
                session.delete(case)
                deleted += 1
                logger.info(f"Rejected (deleted) case {case.case_number}")

        session.commit()

        return jsonify({
            'success': True,
            'deleted': deleted
        })


@review_bp.route('/skipped/add', methods=['POST'])
def add_skipped_cases():
    """
    Add skipped cases as foreclosures.

    Body:
        {"skipped_ids": [1, 2, 3]}

    This fetches fresh data from the portal and saves to cases table.
    """
    data = request.get_json()
    skipped_ids = data.get('skipped_ids', [])

    if not skipped_ids:
        return jsonify({'error': 'No skipped_ids provided'}), 400

    with get_session() as session:
        added = 0
        errors = []

        for skipped_id in skipped_ids:
            skipped = session.query(SkippedCase).filter_by(id=skipped_id).first()
            if not skipped:
                errors.append(f"Skipped case {skipped_id} not found")
                continue

            # Check if case already exists
            existing = session.query(Case).filter_by(case_number=skipped.case_number).first()
            if existing:
                # Mark as reviewed (already exists)
                skipped.reviewed_at = datetime.utcnow()
                skipped.review_action = 'added'
                logger.info(f"Case {skipped.case_number} already exists, marking as reviewed")
                continue

            # Create case from skipped data
            case = Case(
                case_number=skipped.case_number,
                county_code=skipped.county_code,
                county_name=skipped.county_name,
                case_type=skipped.case_type,
                case_status=None,
                file_date=skipped.file_date,
                style=skipped.style,
                case_url=skipped.case_url,
                classification='upcoming'  # Default to upcoming
            )
            session.add(case)
            session.flush()

            # Add events from JSON
            events = json.loads(skipped.events_json) if skipped.events_json else []
            for event_data in events:
                event = CaseEvent(
                    case_id=case.id,
                    event_date=event_data.get('event_date'),
                    event_type=event_data.get('event_type')
                )
                session.add(event)

            # Mark skipped case as reviewed
            skipped.reviewed_at = datetime.utcnow()
            skipped.review_action = 'added'

            added += 1
            logger.info(f"Added skipped case {skipped.case_number} as foreclosure")

        session.commit()

        return jsonify({
            'success': True,
            'added': added,
            'errors': errors
        })


@review_bp.route('/skipped/dismiss', methods=['POST'])
def dismiss_skipped_cases():
    """
    Dismiss skipped cases (confirm they are not foreclosures).

    Body:
        {"skipped_ids": [1, 2, 3]}
    """
    data = request.get_json()
    skipped_ids = data.get('skipped_ids', [])

    if not skipped_ids:
        return jsonify({'error': 'No skipped_ids provided'}), 400

    with get_session() as session:
        dismissed = 0
        for skipped_id in skipped_ids:
            skipped = session.query(SkippedCase).filter_by(id=skipped_id).first()
            if skipped:
                skipped.reviewed_at = datetime.utcnow()
                skipped.review_action = 'dismissed'
                dismissed += 1
                logger.info(f"Dismissed skipped case {skipped.case_number}")

        session.commit()

        return jsonify({
            'success': True,
            'dismissed': dismissed
        })


@review_bp.route('/cleanup', methods=['DELETE'])
def cleanup_old_skipped():
    """
    Remove old dismissed skipped cases.

    Query params:
        days: Number of days to keep (default: 7)
    """
    days = request.args.get('days', 7, type=int)
    cutoff = date.today() - timedelta(days=days)

    with get_session() as session:
        # Delete dismissed skipped cases older than cutoff
        deleted = session.query(SkippedCase).filter(
            SkippedCase.review_action == 'dismissed',
            SkippedCase.scrape_date < cutoff
        ).delete()

        session.commit()

        logger.info(f"Cleaned up {deleted} old dismissed skipped cases")

        return jsonify({
            'success': True,
            'deleted': deleted
        })


@review_bp.route('/pending-count', methods=['GET'])
def get_pending_count():
    """Get count of cases pending review (for badge)."""
    with get_session() as session:
        # Count today's foreclosures
        today = date.today()
        foreclosure_count = session.query(Case).filter(
            func.date(Case.created_at) == today
        ).count()

        # Count pending skipped cases (any date)
        skipped_count = session.query(SkippedCase).filter(
            SkippedCase.review_action.is_(None)
        ).count()

        return jsonify({
            'foreclosures': foreclosure_count,
            'skipped': skipped_count,
            'total': foreclosure_count + skipped_count
        })
```

**Step 2: Register blueprint in app.py**

In `/home/ahn/projects/nc_foreclosures/.worktrees/frontend/web_app/app.py`, add after the cases blueprint registration (around line 42):

```python
    # Register review API
    from web_app.api.review import review_bp
    app.register_blueprint(review_bp, url_prefix='/api/review')
```

**Step 3: Commit**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git add web_app/api/review.py web_app/app.py
git commit -m "feat: add Review Queue API endpoints

- GET /api/review/daily - Get foreclosures and skipped cases by date
- POST /api/review/foreclosures/reject - Delete incorrect foreclosures
- POST /api/review/skipped/add - Add skipped cases as foreclosures
- POST /api/review/skipped/dismiss - Confirm skipped were correct
- DELETE /api/review/cleanup - Remove old dismissed cases
- GET /api/review/pending-count - Badge count for nav"
```

---

## Task 5: Create Review Queue Frontend Page

**Files:**
- Create: `frontend/src/pages/ReviewQueue.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/AppLayout.jsx`
- Create: `frontend/src/api/review.js`

**Step 1: Create API client**

Create `/home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend/src/api/review.js`:

```javascript
const API_BASE = '/api/review';

export async function getDailyReview(date) {
  const params = date ? `?date=${date}` : '';
  const response = await fetch(`${API_BASE}/daily${params}`);
  if (!response.ok) throw new Error('Failed to fetch review data');
  return response.json();
}

export async function rejectForeclosures(caseIds) {
  const response = await fetch(`${API_BASE}/foreclosures/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_ids: caseIds })
  });
  if (!response.ok) throw new Error('Failed to reject foreclosures');
  return response.json();
}

export async function addSkippedCases(skippedIds) {
  const response = await fetch(`${API_BASE}/skipped/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ skipped_ids: skippedIds })
  });
  if (!response.ok) throw new Error('Failed to add skipped cases');
  return response.json();
}

export async function dismissSkippedCases(skippedIds) {
  const response = await fetch(`${API_BASE}/skipped/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ skipped_ids: skippedIds })
  });
  if (!response.ok) throw new Error('Failed to dismiss skipped cases');
  return response.json();
}

export async function getPendingCount() {
  const response = await fetch(`${API_BASE}/pending-count`);
  if (!response.ok) throw new Error('Failed to fetch pending count');
  return response.json();
}
```

**Step 2: Create ReviewQueue page**

Create `/home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend/src/pages/ReviewQueue.jsx`:

```jsx
import { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  DatePicker,
  Space,
  Typography,
  Tag,
  Collapse,
  message,
  Dropdown,
  Popconfirm
} from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  PlusOutlined,
  DeleteOutlined,
  DownOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  getDailyReview,
  rejectForeclosures,
  addSkippedCases,
  dismissSkippedCases
} from '../api/review';

const { Title, Text } = Typography;
const { Panel } = Collapse;

export default function ReviewQueue() {
  const [date, setDate] = useState(dayjs());
  const [data, setData] = useState({ foreclosures: [], skipped: [], counts: {} });
  const [loading, setLoading] = useState(true);
  const [selectedForeclosures, setSelectedForeclosures] = useState([]);
  const [selectedSkipped, setSelectedSkipped] = useState([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const result = await getDailyReview(date.format('YYYY-MM-DD'));
      setData(result);
      setSelectedForeclosures([]);
      setSelectedSkipped([]);
    } catch (error) {
      message.error('Failed to load review data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [date]);

  const handleRejectSelected = async () => {
    if (selectedForeclosures.length === 0) return;
    try {
      await rejectForeclosures(selectedForeclosures);
      message.success(`Rejected ${selectedForeclosures.length} case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to reject cases');
    }
  };

  const handleAddSelected = async () => {
    if (selectedSkipped.length === 0) return;
    try {
      const result = await addSkippedCases(selectedSkipped);
      message.success(`Added ${result.added} case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to add cases');
    }
  };

  const handleDismissSelected = async () => {
    if (selectedSkipped.length === 0) return;
    try {
      await dismissSkippedCases(selectedSkipped);
      message.success(`Dismissed ${selectedSkipped.length} case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to dismiss cases');
    }
  };

  const handleDismissAll = async () => {
    const allIds = data.skipped.map(s => s.id);
    if (allIds.length === 0) return;
    try {
      await dismissSkippedCases(allIds);
      message.success(`Dismissed all ${allIds.length} skipped case(s)`);
      fetchData();
    } catch (error) {
      message.error('Failed to dismiss cases');
    }
  };

  const foreclosureColumns = [
    {
      title: 'Case Number',
      dataIndex: 'case_number',
      key: 'case_number',
      render: (text, record) => (
        <a href={record.case_url} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      )
    },
    {
      title: 'County',
      dataIndex: 'county_name',
      key: 'county_name'
    },
    {
      title: 'Case Type',
      dataIndex: 'case_type',
      key: 'case_type',
      ellipsis: true
    },
    {
      title: 'Style',
      dataIndex: 'style',
      key: 'style',
      ellipsis: true
    },
    {
      title: 'File Date',
      dataIndex: 'file_date',
      key: 'file_date'
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Popconfirm
          title="Reject this case?"
          description="This will delete the case from the database."
          onConfirm={async () => {
            try {
              await rejectForeclosures([record.id]);
              message.success('Case rejected');
              fetchData();
            } catch (error) {
              message.error('Failed to reject case');
            }
          }}
        >
          <Button danger icon={<CloseOutlined />} size="small">
            Reject
          </Button>
        </Popconfirm>
      )
    }
  ];

  const skippedColumns = [
    {
      title: 'Case Number',
      dataIndex: 'case_number',
      key: 'case_number',
      render: (text, record) => (
        <a href={record.case_url} target="_blank" rel="noopener noreferrer">
          {text}
        </a>
      )
    },
    {
      title: 'County',
      dataIndex: 'county_name',
      key: 'county_name'
    },
    {
      title: 'Case Type',
      dataIndex: 'case_type',
      key: 'case_type',
      ellipsis: true
    },
    {
      title: 'Reason',
      dataIndex: 'skip_reason',
      key: 'skip_reason',
      ellipsis: true,
      render: (text) => <Tag color="orange">{text}</Tag>
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size="small"
            onClick={async () => {
              try {
                await addSkippedCases([record.id]);
                message.success('Case added');
                fetchData();
              } catch (error) {
                message.error('Failed to add case');
              }
            }}
          >
            Add
          </Button>
          <Button
            icon={<DeleteOutlined />}
            size="small"
            onClick={async () => {
              try {
                await dismissSkippedCases([record.id]);
                message.success('Case dismissed');
                fetchData();
              } catch (error) {
                message.error('Failed to dismiss case');
              }
            }}
          >
            Dismiss
          </Button>
        </Space>
      )
    }
  ];

  const expandedRowRender = (record) => (
    <div style={{ padding: '8px 0' }}>
      <Text strong>Events:</Text>
      <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
        {record.events?.map((event, idx) => (
          <li key={idx}>
            {event.event_date} - {event.event_type || '(no type)'}
            {event.document_title && (
              <Text type="secondary"> (Doc: {event.document_title})</Text>
            )}
          </li>
        ))}
        {(!record.events || record.events.length === 0) && (
          <li><Text type="secondary">No events</Text></li>
        )}
      </ul>
    </div>
  );

  const foreclosureBulkMenu = {
    items: [
      {
        key: 'reject',
        label: `Reject Selected (${selectedForeclosures.length})`,
        icon: <CloseOutlined />,
        danger: true,
        disabled: selectedForeclosures.length === 0,
        onClick: handleRejectSelected
      }
    ]
  };

  const skippedBulkMenu = {
    items: [
      {
        key: 'add',
        label: `Add Selected (${selectedSkipped.length})`,
        icon: <PlusOutlined />,
        disabled: selectedSkipped.length === 0,
        onClick: handleAddSelected
      },
      {
        key: 'dismiss',
        label: `Dismiss Selected (${selectedSkipped.length})`,
        icon: <DeleteOutlined />,
        disabled: selectedSkipped.length === 0,
        onClick: handleDismissSelected
      },
      { type: 'divider' },
      {
        key: 'dismissAll',
        label: 'Dismiss All',
        icon: <DeleteOutlined />,
        danger: true,
        disabled: data.skipped.length === 0,
        onClick: handleDismissAll
      }
    ]
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>Review Queue</Title>
        <DatePicker
          value={date}
          onChange={(d) => d && setDate(d)}
          allowClear={false}
        />
      </div>

      <Collapse defaultActiveKey={['foreclosures', 'skipped']}>
        <Panel
          header={
            <Space>
              <CheckOutlined style={{ color: '#52c41a' }} />
              <span>Foreclosures ({data.counts.foreclosures || 0} cases)</span>
            </Space>
          }
          key="foreclosures"
          extra={
            <Dropdown menu={foreclosureBulkMenu} trigger={['click']}>
              <Button onClick={(e) => e.stopPropagation()}>
                Bulk Actions <DownOutlined />
              </Button>
            </Dropdown>
          }
        >
          <Table
            rowKey="id"
            columns={foreclosureColumns}
            dataSource={data.foreclosures}
            loading={loading}
            pagination={{ pageSize: 10 }}
            expandable={{ expandedRowRender }}
            rowSelection={{
              selectedRowKeys: selectedForeclosures,
              onChange: setSelectedForeclosures
            }}
            size="small"
          />
        </Panel>

        <Panel
          header={
            <Space>
              <CloseOutlined style={{ color: '#faad14' }} />
              <span>Skipped ({data.counts.skipped || 0} cases)</span>
            </Space>
          }
          key="skipped"
          extra={
            <Dropdown menu={skippedBulkMenu} trigger={['click']}>
              <Button onClick={(e) => e.stopPropagation()}>
                Bulk Actions <DownOutlined />
              </Button>
            </Dropdown>
          }
        >
          <Table
            rowKey="id"
            columns={skippedColumns}
            dataSource={data.skipped}
            loading={loading}
            pagination={{ pageSize: 10 }}
            expandable={{ expandedRowRender }}
            rowSelection={{
              selectedRowKeys: selectedSkipped,
              onChange: setSelectedSkipped
            }}
            size="small"
          />
        </Panel>
      </Collapse>
    </div>
  );
}
```

**Step 3: Add route to App.jsx**

In `/home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend/src/App.jsx`:

Add import at top (after line 8):
```jsx
import ReviewQueue from './pages/ReviewQueue';
```

Add route inside the protected routes (after line 64, after Settings route):
```jsx
            <Route path="/review" element={<ReviewQueue />} />
```

**Step 4: Add nav item to AppLayout**

First, read the current AppLayout to understand its structure:

The file is at `/home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend/src/components/AppLayout.jsx`. Add a "Review Queue" menu item with a badge showing pending count.

Add to imports:
```jsx
import { useState, useEffect } from 'react';
import { Badge } from 'antd';
import { AuditOutlined } from '@ant-design/icons';
```

Add to menu items array (after Settings):
```jsx
    {
      key: '/review',
      icon: <Badge count={pendingCount} size="small"><AuditOutlined /></Badge>,
      label: 'Review Queue',
    },
```

Add state and effect for pending count:
```jsx
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    fetch('/api/review/pending-count')
      .then(res => res.json())
      .then(data => setPendingCount(data.total || 0))
      .catch(() => {});
  }, []);
```

**Step 5: Install dayjs dependency**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend
npm install dayjs
```

**Step 6: Commit**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git add frontend/src/api/review.js frontend/src/pages/ReviewQueue.jsx frontend/src/App.jsx frontend/src/components/AppLayout.jsx frontend/package.json frontend/package-lock.json
git commit -m "feat: add Review Queue frontend page

- ReviewQueue page with Foreclosures and Skipped sections
- Expandable rows showing events with document titles
- Bulk actions: Reject, Add, Dismiss, Dismiss All
- Date picker to review past days
- Badge in nav showing pending review count"
```

---

## Task 6: Sync Changes to Main Branch

**Step 1: Copy modified files from main to worktree**

The database and scraper changes were made in main. Copy them to the frontend worktree:

```bash
cd /home/ahn/projects/nc_foreclosures

# Copy database changes
cp database/schema.sql .worktrees/frontend/database/
cp database/models.py .worktrees/frontend/database/

# Copy scraper changes
cp scraper/page_parser.py .worktrees/frontend/scraper/
cp scraper/date_range_scrape.py .worktrees/frontend/scraper/
```

**Step 2: Commit in worktree**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git add database/ scraper/
git commit -m "sync: bring in database and scraper changes from main"
```

**Step 3: Merge worktree to main (or create PR)**

Option A - Direct merge:
```bash
cd /home/ahn/projects/nc_foreclosures
git merge feature/frontend -m "Merge Review Queue feature from frontend worktree"
```

Option B - Create PR (recommended):
```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git push -u origin feature/frontend
gh pr create --title "Add Review Queue for classification enhancement" --body "..."
```

---

## Task 7: Test End-to-End

**Step 1: Start PostgreSQL**

```bash
sudo service postgresql start
```

**Step 2: Run database migration**

```bash
cd /home/ahn/projects/nc_foreclosures
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
CREATE TABLE IF NOT EXISTS skipped_cases (
    id SERIAL PRIMARY KEY,
    case_number VARCHAR(50) NOT NULL,
    county_code VARCHAR(10) NOT NULL,
    county_name VARCHAR(50) NOT NULL,
    case_url TEXT,
    case_type VARCHAR(100),
    style TEXT,
    file_date DATE,
    events_json JSONB,
    skip_reason VARCHAR(255),
    scrape_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    review_action VARCHAR(20)
);
CREATE INDEX IF NOT EXISTS idx_skipped_cases_scrape_date ON skipped_cases(scrape_date);
CREATE INDEX IF NOT EXISTS idx_skipped_cases_reviewed ON skipped_cases(reviewed_at);
"
```

**Step 3: Start backend API**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
source venv/bin/activate
export PYTHONPATH=$(pwd)
python web_app/app.py
```

**Step 4: Start frontend**

In new terminal:
```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend
npm run dev
```

**Step 5: Test API endpoints**

```bash
# Get today's review queue
curl http://localhost:5000/api/review/daily

# Get pending count
curl http://localhost:5000/api/review/pending-count
```

**Step 6: Test in browser**

1. Open http://localhost:5173
2. Navigate to Review Queue
3. Verify both sections show
4. Test expanding rows
5. Test bulk actions

**Step 7: Final commit**

```bash
git add -A
git commit -m "test: verify Review Queue end-to-end functionality"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add skipped_cases table | `database/schema.sql`, `database/models.py` |
| 2 | Add document title detection | `scraper/page_parser.py` |
| 3 | Log skipped cases in scraper | `scraper/date_range_scrape.py` |
| 4 | Create Review API endpoints | `web_app/api/review.py`, `web_app/app.py` |
| 5 | Create Review Queue frontend | `frontend/src/pages/ReviewQueue.jsx`, etc. |
| 6 | Sync and merge changes | Git operations |
| 7 | End-to-end testing | Manual verification |

**Total estimated implementation:** 7 tasks, ~45 minutes with subagent execution.
