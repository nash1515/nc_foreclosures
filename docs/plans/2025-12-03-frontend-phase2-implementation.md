# Frontend Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the All Cases page with filtering/search, Case Detail page with full info display, and watchlist functionality.

**Architecture:** Flask API endpoints serve case data from PostgreSQL. React frontend uses Ant Design Table with server-side pagination. Watchlist stored per-user in database. All API calls go through Vite proxy to Flask.

**Tech Stack:** Flask, SQLAlchemy, React, Ant Design Table, axios

---

## Task 1: Create Watchlist Database Table

**Files:**
- Create: `database/migrations/add_watchlist_table.sql`
- Modify: `database/models.py`

**Step 1: Create SQL migration file**

Create `database/migrations/add_watchlist_table.sql`:

```sql
-- Watchlist table for user's starred cases
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, case_id)
);

-- Index for fast lookups by user
CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON watchlist(user_id);
-- Index for fast lookups by case
CREATE INDEX IF NOT EXISTS idx_watchlist_case_id ON watchlist(case_id);
```

**Step 2: Run migration**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f database/migrations/add_watchlist_table.sql
```

Expected: `CREATE TABLE`, `CREATE INDEX` x2

**Step 3: Add Watchlist model to models.py**

Add after the User class (around line 25) in `database/models.py`:

```python
class Watchlist(Base):
    """User's starred/watchlisted cases."""

    __tablename__ = 'watchlist'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    user = relationship("User")
    case = relationship("Case")

    def __repr__(self):
        return f"<Watchlist(user_id={self.user_id}, case_id={self.case_id})>"
```

**Step 4: Verify table exists**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d watchlist"
```

**Step 5: Commit**

```bash
git add database/migrations/add_watchlist_table.sql database/models.py
git commit -m "feat: add watchlist table for user's starred cases"
```

---

## Task 2: Create Cases API Endpoint (List with Filters)

**Files:**
- Create: `web_app/api/cases.py`
- Modify: `web_app/app.py`

**Step 1: Create cases API module**

Create `web_app/api/cases.py`:

```python
"""Cases API endpoints."""

from flask import Blueprint, jsonify, request
from flask_dance.contrib.google import google
from sqlalchemy import or_, and_
from database.connection import get_session
from database.models import Case, Party, Watchlist, User
from datetime import datetime

cases_bp = Blueprint('cases', __name__)


def get_current_user_id():
    """Get current user's ID from session."""
    if not google.authorized:
        return None

    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        return None

    email = resp.json().get('email')
    with get_session() as db_session:
        user = db_session.query(User).filter_by(email=email).first()
        return user.id if user else None


@cases_bp.route('', methods=['GET'])
def list_cases():
    """List cases with filters and pagination.

    Query params:
    - page: Page number (default 1)
    - page_size: Items per page (default 20, max 100)
    - classification: Filter by classification (comma-separated for multiple)
    - county: Filter by county code (comma-separated for multiple)
    - search: Search case_number, property_address, or party names
    - start_date: Filter file_date >= start_date (YYYY-MM-DD)
    - end_date: Filter file_date <= end_date (YYYY-MM-DD)
    - watchlist_only: If 'true', only show watchlisted cases
    - sort_by: Column to sort by (default: file_date)
    - sort_order: 'asc' or 'desc' (default: desc)
    """
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()

    # Parse query params
    page = request.args.get('page', 1, type=int)
    page_size = min(request.args.get('page_size', 20, type=int), 100)
    classification = request.args.get('classification', '')
    county = request.args.get('county', '')
    search = request.args.get('search', '').strip()
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    watchlist_only = request.args.get('watchlist_only', 'false').lower() == 'true'
    sort_by = request.args.get('sort_by', 'file_date')
    sort_order = request.args.get('sort_order', 'desc')

    with get_session() as db_session:
        # Base query
        query = db_session.query(Case)

        # Classification filter
        if classification:
            classifications = [c.strip() for c in classification.split(',')]
            query = query.filter(Case.classification.in_(classifications))

        # County filter
        if county:
            counties = [c.strip() for c in county.split(',')]
            query = query.filter(Case.county_code.in_(counties))

        # Date range filter
        if start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Case.file_date >= start)
            except ValueError:
                pass

        if end_date:
            try:
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Case.file_date <= end)
            except ValueError:
                pass

        # Search filter (case number, address, or party name)
        if search:
            search_pattern = f'%{search}%'
            # Subquery for party name search
            party_case_ids = db_session.query(Party.case_id).filter(
                Party.party_name.ilike(search_pattern)
            ).distinct()

            query = query.filter(
                or_(
                    Case.case_number.ilike(search_pattern),
                    Case.property_address.ilike(search_pattern),
                    Case.style.ilike(search_pattern),
                    Case.id.in_(party_case_ids)
                )
            )

        # Watchlist filter
        if watchlist_only and user_id:
            watchlist_case_ids = db_session.query(Watchlist.case_id).filter(
                Watchlist.user_id == user_id
            )
            query = query.filter(Case.id.in_(watchlist_case_ids))

        # Get total count before pagination
        total = query.count()

        # Sorting
        sort_column = getattr(Case, sort_by, Case.file_date)
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Pagination
        offset = (page - 1) * page_size
        cases = query.offset(offset).limit(page_size).all()

        # Get watchlist status for current user
        watchlist_case_ids = set()
        if user_id:
            watchlist_items = db_session.query(Watchlist.case_id).filter(
                Watchlist.user_id == user_id,
                Watchlist.case_id.in_([c.id for c in cases])
            ).all()
            watchlist_case_ids = {w.case_id for w in watchlist_items}

        # Serialize
        result = []
        for case in cases:
            result.append({
                'id': case.id,
                'case_number': case.case_number,
                'county_code': case.county_code,
                'county_name': case.county_name,
                'style': case.style,
                'classification': case.classification,
                'file_date': case.file_date.isoformat() if case.file_date else None,
                'property_address': case.property_address,
                'current_bid_amount': float(case.current_bid_amount) if case.current_bid_amount else None,
                'next_bid_deadline': case.next_bid_deadline.isoformat() if case.next_bid_deadline else None,
                'is_watchlisted': case.id in watchlist_case_ids
            })

        return jsonify({
            'cases': result,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        })
```

**Step 2: Register blueprint in app.py**

Add to `web_app/app.py` after the existing blueprint registrations (around line 32):

```python
    # Register cases API
    from web_app.api.cases import cases_bp
    app.register_blueprint(cases_bp, url_prefix='/api/cases')
```

**Step 3: Test the endpoint**

```bash
curl -s http://localhost:5000/api/cases | head -100
```

Expected: 401 (not authenticated) - this is correct for now.

**Step 4: Commit**

```bash
git add web_app/api/cases.py web_app/app.py
git commit -m "feat: add cases list API with filters and pagination"
```

---

## Task 3: Create Case Detail API Endpoint

**Files:**
- Modify: `web_app/api/cases.py`

**Step 1: Add case detail endpoint**

Add to `web_app/api/cases.py` after the `list_cases` function:

```python
@cases_bp.route('/<int:case_id>', methods=['GET'])
def get_case(case_id):
    """Get full case detail including parties, events, and upset bidders."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()

    with get_session() as db_session:
        case = db_session.query(Case).filter_by(id=case_id).first()

        if not case:
            return jsonify({'error': 'Case not found'}), 404

        # Check if watchlisted
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

        # Get events sorted by date (newest first)
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

        # Extract upset bidders from events (events with "Upset Bid" type)
        upset_bidders = []
        for event in case.events:
            if event.event_type and 'upset' in event.event_type.lower():
                # Try to parse bidder info from description or filed_by
                upset_bidders.append({
                    'date': event.event_date.isoformat() if event.event_date else None,
                    'bidder': event.filed_by or 'Unknown',
                    'amount': None  # Amount would need to be parsed from description
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
            'parties': parties,
            'events': events,
            'hearings': hearings,
            'upset_bidders': upset_bidders,
            'is_watchlisted': is_watchlisted,
            'photo_url': None  # Placeholder for future enrichment
        })
```

**Step 2: Import datetime at top of file**

Ensure this import is at the top of `web_app/api/cases.py`:

```python
from datetime import datetime
```

**Step 3: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: add case detail API endpoint"
```

---

## Task 4: Create Watchlist API Endpoints

**Files:**
- Modify: `web_app/api/cases.py`

**Step 1: Add watchlist endpoints**

Add to `web_app/api/cases.py`:

```python
@cases_bp.route('/<int:case_id>/watchlist', methods=['POST'])
def add_to_watchlist(case_id):
    """Add a case to user's watchlist."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    with get_session() as db_session:
        # Check if case exists
        case = db_session.query(Case).filter_by(id=case_id).first()
        if not case:
            return jsonify({'error': 'Case not found'}), 404

        # Check if already watchlisted
        existing = db_session.query(Watchlist).filter_by(
            user_id=user_id, case_id=case_id
        ).first()

        if existing:
            return jsonify({'message': 'Already in watchlist', 'is_watchlisted': True})

        # Add to watchlist
        watchlist = Watchlist(user_id=user_id, case_id=case_id)
        db_session.add(watchlist)
        db_session.commit()

        return jsonify({'message': 'Added to watchlist', 'is_watchlisted': True})


@cases_bp.route('/<int:case_id>/watchlist', methods=['DELETE'])
def remove_from_watchlist(case_id):
    """Remove a case from user's watchlist."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    with get_session() as db_session:
        watchlist = db_session.query(Watchlist).filter_by(
            user_id=user_id, case_id=case_id
        ).first()

        if watchlist:
            db_session.delete(watchlist)
            db_session.commit()

        return jsonify({'message': 'Removed from watchlist', 'is_watchlisted': False})
```

**Step 2: Commit**

```bash
git add web_app/api/cases.py
git commit -m "feat: add watchlist toggle API endpoints"
```

---

## Task 5: Create API Client for Frontend

**Files:**
- Create: `frontend/src/api/cases.js`

**Step 1: Create API client module**

Create `frontend/src/api/cases.js`:

```javascript
/**
 * Cases API client
 */

const API_BASE = '/api';

/**
 * Fetch cases with filters and pagination
 */
export async function fetchCases({
  page = 1,
  pageSize = 20,
  classification = '',
  county = '',
  search = '',
  startDate = '',
  endDate = '',
  watchlistOnly = false,
  sortBy = 'file_date',
  sortOrder = 'desc'
} = {}) {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
    sort_by: sortBy,
    sort_order: sortOrder
  });

  if (classification) params.append('classification', classification);
  if (county) params.append('county', county);
  if (search) params.append('search', search);
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  if (watchlistOnly) params.append('watchlist_only', 'true');

  const response = await fetch(`${API_BASE}/cases?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch cases');
  }
  return response.json();
}

/**
 * Fetch single case detail
 */
export async function fetchCase(caseId) {
  const response = await fetch(`${API_BASE}/cases/${caseId}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Case not found');
    }
    throw new Error('Failed to fetch case');
  }
  return response.json();
}

/**
 * Add case to watchlist
 */
export async function addToWatchlist(caseId) {
  const response = await fetch(`${API_BASE}/cases/${caseId}/watchlist`, {
    method: 'POST'
  });
  if (!response.ok) {
    throw new Error('Failed to add to watchlist');
  }
  return response.json();
}

/**
 * Remove case from watchlist
 */
export async function removeFromWatchlist(caseId) {
  const response = await fetch(`${API_BASE}/cases/${caseId}/watchlist`, {
    method: 'DELETE'
  });
  if (!response.ok) {
    throw new Error('Failed to remove from watchlist');
  }
  return response.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/cases.js
git commit -m "feat: add cases API client for frontend"
```

---

## Task 6: Build CaseList Page with Filters

**Files:**
- Modify: `frontend/src/pages/CaseList.jsx`

**Step 1: Replace CaseList.jsx with full implementation**

Replace entire contents of `frontend/src/pages/CaseList.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Typography, Table, Input, Select, DatePicker, Space, Tag, Button, Switch, message
} from 'antd';
import { StarOutlined, StarFilled, SearchOutlined } from '@ant-design/icons';
import { fetchCases, addToWatchlist, removeFromWatchlist } from '../api/cases';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

// County options
const COUNTIES = [
  { value: '180', label: 'Chatham' },
  { value: '310', label: 'Durham' },
  { value: '420', label: 'Harnett' },
  { value: '520', label: 'Lee' },
  { value: '670', label: 'Orange' },
  { value: '910', label: 'Wake' },
];

// Classification options with colors
const CLASSIFICATIONS = [
  { value: 'upcoming', label: 'Upcoming', color: 'blue' },
  { value: 'upset_bid', label: 'Upset Bid', color: 'red' },
  { value: 'blocked', label: 'Blocked', color: 'orange' },
  { value: 'closed_sold', label: 'Closed (Sold)', color: 'green' },
  { value: 'closed_dismissed', label: 'Closed (Dismissed)', color: 'default' },
];

function CaseList() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [sorter, setSorter] = useState({ field: 'file_date', order: 'descend' });

  // Filters
  const [search, setSearch] = useState('');
  const [classification, setClassification] = useState([]);
  const [county, setCounty] = useState([]);
  const [dateRange, setDateRange] = useState(null);
  const [watchlistOnly, setWatchlistOnly] = useState(false);

  const loadCases = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchCases({
        page: pagination.current,
        pageSize: pagination.pageSize,
        classification: classification.join(','),
        county: county.join(','),
        search,
        startDate: dateRange?.[0]?.format('YYYY-MM-DD') || '',
        endDate: dateRange?.[1]?.format('YYYY-MM-DD') || '',
        watchlistOnly,
        sortBy: sorter.field || 'file_date',
        sortOrder: sorter.order === 'ascend' ? 'asc' : 'desc'
      });
      setCases(result.cases);
      setTotal(result.total);
    } catch (error) {
      message.error('Failed to load cases');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [pagination, classification, county, search, dateRange, watchlistOnly, sorter]);

  useEffect(() => {
    loadCases();
  }, [loadCases]);

  const handleTableChange = (newPagination, filters, newSorter) => {
    setPagination({
      current: newPagination.current,
      pageSize: newPagination.pageSize
    });
    if (newSorter.field) {
      setSorter({
        field: newSorter.field,
        order: newSorter.order
      });
    }
  };

  const handleSearch = (value) => {
    setSearch(value);
    setPagination(prev => ({ ...prev, current: 1 }));
  };

  const handleWatchlistToggle = async (caseId, currentlyWatchlisted) => {
    try {
      if (currentlyWatchlisted) {
        await removeFromWatchlist(caseId);
        message.success('Removed from watchlist');
      } else {
        await addToWatchlist(caseId);
        message.success('Added to watchlist');
      }
      // Update local state
      setCases(prev => prev.map(c =>
        c.id === caseId ? { ...c, is_watchlisted: !currentlyWatchlisted } : c
      ));
    } catch (error) {
      message.error('Failed to update watchlist');
    }
  };

  const columns = [
    {
      title: '',
      dataIndex: 'is_watchlisted',
      key: 'watchlist',
      width: 50,
      render: (isWatchlisted, record) => (
        <Button
          type="text"
          icon={isWatchlisted ? <StarFilled style={{ color: '#faad14' }} /> : <StarOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            handleWatchlistToggle(record.id, isWatchlisted);
          }}
        />
      )
    },
    {
      title: 'Case Number',
      dataIndex: 'case_number',
      key: 'case_number',
      sorter: true,
      render: (text, record) => (
        <Link to={`/cases/${record.id}`}>{text}</Link>
      )
    },
    {
      title: 'Style',
      dataIndex: 'style',
      key: 'style',
      ellipsis: true,
      width: 300
    },
    {
      title: 'County',
      dataIndex: 'county_name',
      key: 'county_name',
      sorter: true,
      width: 100
    },
    {
      title: 'Classification',
      dataIndex: 'classification',
      key: 'classification',
      width: 140,
      render: (value) => {
        const config = CLASSIFICATIONS.find(c => c.value === value);
        return config ? (
          <Tag color={config.color}>{config.label}</Tag>
        ) : (
          <Tag>{value || 'Unknown'}</Tag>
        );
      }
    },
    {
      title: 'File Date',
      dataIndex: 'file_date',
      key: 'file_date',
      sorter: true,
      width: 110,
      render: (date) => date ? dayjs(date).format('MM/DD/YYYY') : '-'
    },
    {
      title: 'Current Bid',
      dataIndex: 'current_bid_amount',
      key: 'current_bid_amount',
      sorter: true,
      width: 120,
      align: 'right',
      render: (amount) => amount ? `$${amount.toLocaleString()}` : '-'
    },
    {
      title: 'Deadline',
      dataIndex: 'next_bid_deadline',
      key: 'next_bid_deadline',
      sorter: true,
      width: 110,
      render: (date) => date ? dayjs(date).format('MM/DD/YYYY') : '-'
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>All Cases</Title>

      {/* Filters */}
      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Search case #, address, party..."
          allowClear
          onSearch={handleSearch}
          style={{ width: 280 }}
          prefix={<SearchOutlined />}
        />

        <Select
          mode="multiple"
          placeholder="Classification"
          style={{ minWidth: 180 }}
          value={classification}
          onChange={(value) => {
            setClassification(value);
            setPagination(prev => ({ ...prev, current: 1 }));
          }}
          options={CLASSIFICATIONS.map(c => ({ value: c.value, label: c.label }))}
          allowClear
        />

        <Select
          mode="multiple"
          placeholder="County"
          style={{ minWidth: 150 }}
          value={county}
          onChange={(value) => {
            setCounty(value);
            setPagination(prev => ({ ...prev, current: 1 }));
          }}
          options={COUNTIES}
          allowClear
        />

        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            setDateRange(dates);
            setPagination(prev => ({ ...prev, current: 1 }));
          }}
          format="MM/DD/YYYY"
          placeholder={['Start Date', 'End Date']}
        />

        <Space>
          <span>Watchlist Only:</span>
          <Switch
            checked={watchlistOnly}
            onChange={(checked) => {
              setWatchlistOnly(checked);
              setPagination(prev => ({ ...prev, current: 1 }));
            }}
          />
        </Space>
      </Space>

      {/* Table */}
      <Table
        columns={columns}
        dataSource={cases}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          total,
          showSizeChanger: true,
          showTotal: (total) => `${total} cases`
        }}
        onChange={handleTableChange}
        size="middle"
      />
    </div>
  );
}

export default CaseList;
```

**Step 2: Install dayjs dependency**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend
npm install dayjs
```

**Step 3: Test frontend compiles**

```bash
npm run build
```

Expected: No errors

**Step 4: Commit**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git add frontend/src/pages/CaseList.jsx frontend/package.json frontend/package-lock.json
git commit -m "feat: build CaseList page with filters, sorting, and watchlist"
```

---

## Task 7: Build CaseDetail Page

**Files:**
- Modify: `frontend/src/pages/CaseDetail.jsx`

**Step 1: Replace CaseDetail.jsx with full implementation**

Replace entire contents of `frontend/src/pages/CaseDetail.jsx`:

```jsx
import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Typography, Card, Row, Col, Tag, Button, Descriptions, Timeline, Table,
  Spin, Alert, Space, Divider, message, Image
} from 'antd';
import {
  ArrowLeftOutlined, StarOutlined, StarFilled,
  LinkOutlined, FileTextOutlined, PictureOutlined
} from '@ant-design/icons';
import { fetchCase, addToWatchlist, removeFromWatchlist } from '../api/cases';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

// Classification colors
const CLASSIFICATION_COLORS = {
  upcoming: 'blue',
  upset_bid: 'red',
  blocked: 'orange',
  closed_sold: 'green',
  closed_dismissed: 'default'
};

function CaseDetail() {
  const { id } = useParams();
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  const handleWatchlistToggle = async () => {
    if (!caseData) return;

    try {
      if (caseData.is_watchlisted) {
        await removeFromWatchlist(caseData.id);
        message.success('Removed from watchlist');
      } else {
        await addToWatchlist(caseData.id);
        message.success('Added to watchlist');
      }
      setCaseData(prev => ({ ...prev, is_watchlisted: !prev.is_watchlisted }));
    } catch (err) {
      message.error('Failed to update watchlist');
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px' }}>
        <Alert type="error" message={error} showIcon />
        <Link to="/cases" style={{ marginTop: 16, display: 'inline-block' }}>
          <Button icon={<ArrowLeftOutlined />}>Back to Cases</Button>
        </Link>
      </div>
    );
  }

  const c = caseData;
  const daysUntilDeadline = c.next_bid_deadline
    ? dayjs(c.next_bid_deadline).diff(dayjs(), 'day')
    : null;

  return (
    <div style={{ padding: '24px' }}>
      {/* Header */}
      <Space style={{ marginBottom: 16 }}>
        <Link to="/cases">
          <Button icon={<ArrowLeftOutlined />}>Back to Cases</Button>
        </Link>
        <Title level={4} style={{ margin: 0 }}>{c.case_number}</Title>
        <Button
          type={c.is_watchlisted ? 'primary' : 'default'}
          icon={c.is_watchlisted ? <StarFilled /> : <StarOutlined />}
          onClick={handleWatchlistToggle}
        >
          {c.is_watchlisted ? 'Watchlisted' : 'Add to Watchlist'}
        </Button>
      </Space>

      {/* Case Title and Status */}
      <Card style={{ marginBottom: 16 }}>
        <Title level={4} style={{ marginTop: 0 }}>{c.style || c.case_number}</Title>
        <Space>
          <Text type="secondary">{c.county_name} County</Text>
          <Text type="secondary">|</Text>
          <Text type="secondary">Filed: {c.file_date ? dayjs(c.file_date).format('MM/DD/YYYY') : '-'}</Text>
          <Text type="secondary">|</Text>
          <Text type="secondary">Status: {c.case_status || '-'}</Text>
        </Space>
        <div style={{ marginTop: 8 }}>
          <Tag color={CLASSIFICATION_COLORS[c.classification] || 'default'}>
            {c.classification?.replace('_', ' ').toUpperCase() || 'UNKNOWN'}
          </Tag>
          {daysUntilDeadline !== null && daysUntilDeadline >= 0 && (
            <Tag color={daysUntilDeadline <= 3 ? 'red' : 'orange'}>
              Deadline: {dayjs(c.next_bid_deadline).format('MMM D')} ({daysUntilDeadline} days)
            </Tag>
          )}
        </div>
      </Card>

      <Row gutter={16}>
        {/* Left Column - Property & Photo */}
        <Col xs={24} lg={12}>
          <Card title="Property" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={c.photo_url ? 16 : 24}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="Address">
                    {c.property_address || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="Legal Description">
                    <Text ellipsis={{ tooltip: c.legal_description }}>
                      {c.legal_description || '-'}
                    </Text>
                  </Descriptions.Item>
                </Descriptions>

                {/* Enrichment Links Placeholder */}
                <Divider style={{ margin: '12px 0' }} />
                <Space wrap>
                  <Button size="small" icon={<LinkOutlined />} disabled>
                    Zillow
                  </Button>
                  <Button size="small" icon={<LinkOutlined />} disabled>
                    Propwire
                  </Button>
                  <Button size="small" icon={<LinkOutlined />} disabled>
                    County Records
                  </Button>
                  <Button size="small" icon={<FileTextOutlined />} disabled>
                    Deed
                  </Button>
                </Space>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Enrichment links coming in Phase 5
                  </Text>
                </div>
              </Col>
              {/* Photo placeholder */}
              <Col span={c.photo_url ? 8 : 0}>
                {c.photo_url ? (
                  <Image src={c.photo_url} alt="Property" style={{ maxWidth: '100%' }} />
                ) : (
                  <div style={{
                    width: 120, height: 90, background: '#f5f5f5',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: '1px dashed #d9d9d9', borderRadius: 4
                  }}>
                    <PictureOutlined style={{ fontSize: 24, color: '#bfbfbf' }} />
                  </div>
                )}
              </Col>
            </Row>
          </Card>

          {/* Parties */}
          <Card title="Parties" style={{ marginBottom: 16 }}>
            {c.parties && Object.keys(c.parties).length > 0 ? (
              <Descriptions column={1} size="small">
                {Object.entries(c.parties).map(([type, names]) => (
                  <Descriptions.Item key={type} label={type}>
                    {names.join(', ')}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            ) : (
              <Text type="secondary">No parties on record</Text>
            )}
          </Card>

          {/* Upset Bidders */}
          {c.upset_bidders && c.upset_bidders.length > 0 && (
            <Card title="Upset Bidders" style={{ marginBottom: 16 }}>
              <Table
                dataSource={c.upset_bidders}
                rowKey={(r, i) => i}
                size="small"
                pagination={false}
                columns={[
                  { title: 'Date', dataIndex: 'date', render: d => d ? dayjs(d).format('MM/DD/YYYY') : '-' },
                  { title: 'Bidder', dataIndex: 'bidder' },
                  { title: 'Amount', dataIndex: 'amount', render: a => a ? `$${a.toLocaleString()}` : '-' }
                ]}
              />
            </Card>
          )}
        </Col>

        {/* Right Column - Bid Info & Events */}
        <Col xs={24} lg={12}>
          {/* Bid Information */}
          <Card title="Bid Information" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Current Bid">
                <Text strong style={{ fontSize: 16 }}>
                  {c.current_bid_amount ? `$${c.current_bid_amount.toLocaleString()}` : '-'}
                </Text>
              </Descriptions.Item>
              <Descriptions.Item label="Minimum Next Bid">
                {c.minimum_next_bid ? `$${c.minimum_next_bid.toLocaleString()}` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Sale Date">
                {c.sale_date ? dayjs(c.sale_date).format('MM/DD/YYYY') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Bid Deadline">
                {c.next_bid_deadline ? dayjs(c.next_bid_deadline).format('MM/DD/YYYY h:mm A') : '-'}
              </Descriptions.Item>
            </Descriptions>

            <Divider style={{ margin: '12px 0' }} />

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
          </Card>

          {/* Attorney Info */}
          {(c.attorney_name || c.trustee_name) && (
            <Card title="Contacts" style={{ marginBottom: 16 }}>
              <Descriptions column={1} size="small">
                {c.trustee_name && (
                  <Descriptions.Item label="Trustee">{c.trustee_name}</Descriptions.Item>
                )}
                {c.attorney_name && (
                  <Descriptions.Item label="Attorney">{c.attorney_name}</Descriptions.Item>
                )}
                {c.attorney_phone && (
                  <Descriptions.Item label="Phone">{c.attorney_phone}</Descriptions.Item>
                )}
                {c.attorney_email && (
                  <Descriptions.Item label="Email">{c.attorney_email}</Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          )}

          {/* Events Timeline */}
          <Card title="Events Timeline" style={{ marginBottom: 16 }}>
            {c.events && c.events.length > 0 ? (
              <Timeline
                items={c.events.slice(0, 10).map(event => ({
                  children: (
                    <div>
                      <Text strong>{event.date ? dayjs(event.date).format('MM/DD/YYYY') : 'No date'}</Text>
                      <br />
                      <Text>{event.type || event.description || 'Event'}</Text>
                      {event.filed_by && <Text type="secondary"> - {event.filed_by}</Text>}
                    </div>
                  )
                }))}
              />
            ) : (
              <Text type="secondary">No events on record</Text>
            )}
            {c.events && c.events.length > 10 && (
              <Text type="secondary">Showing 10 of {c.events.length} events</Text>
            )}
          </Card>
        </Col>
      </Row>

      {/* Case Link */}
      {c.case_url && (
        <Card size="small">
          <a href={c.case_url} target="_blank" rel="noopener noreferrer">
            <Button icon={<LinkOutlined />}>View on NC Courts Portal</Button>
          </a>
        </Card>
      )}
    </div>
  );
}

export default CaseDetail;
```

**Step 2: Test frontend compiles**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend/frontend
npm run build
```

Expected: No errors

**Step 3: Commit**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git add frontend/src/pages/CaseDetail.jsx
git commit -m "feat: build CaseDetail page with full info display"
```

---

## Task 8: Test Full Integration

**Step 1: Ensure services are running**

```bash
# PostgreSQL
echo "ahn" | sudo -S service postgresql status

# API (in background)
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
pkill -f "web_app/app.py" || true
PYTHONPATH=$(pwd) venv/bin/python web_app/app.py &
sleep 3

# Frontend
cd frontend
npm run dev &
sleep 3
```

**Step 2: Test API endpoints**

```bash
# Health check
curl -s http://localhost:5000/api/health

# Cases list (will return 401 - need to be authenticated)
curl -s http://localhost:5000/api/cases
```

**Step 3: Test in browser**

1. Open http://localhost:5173
2. Sign in with Google
3. Navigate to "All Cases" - should see table with real data
4. Test filters (classification, county, search, date range)
5. Click a case number - should see full case detail
6. Toggle watchlist star - should persist

**Step 4: Commit final state**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git add -A
git commit -m "feat: complete Phase 2 - Cases list, detail, and watchlist"
git push
```

---

## Phase 2 Complete Checklist

- [ ] Watchlist table created in database
- [ ] Watchlist model added to models.py
- [ ] GET /api/cases endpoint with filters and pagination
- [ ] GET /api/cases/:id endpoint with full detail
- [ ] POST/DELETE /api/cases/:id/watchlist endpoints
- [ ] CaseList page with Ant Design table
- [ ] Filters: classification, county, search, date range, watchlist only
- [ ] Sorting and pagination working
- [ ] Watchlist toggle (star) working
- [ ] CaseDetail page with full info
- [ ] Property photo placeholder
- [ ] Enrichment links placeholders
- [ ] Bid ladder display (read-only)
- [ ] Events timeline
- [ ] Upset bidders table

## Next Phase Preview

Phase 3 will implement:
- Team notes (add, view with timestamps/authors)
- Bid ladder editing (initial, 2nd, max)
- Case notes table in database
