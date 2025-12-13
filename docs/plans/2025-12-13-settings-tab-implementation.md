# Settings Tab Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Settings page with Manual Scrape controls and User Management for admin users.

**Architecture:** Role-based access (admin/user) with whitelist authentication. Admin users can trigger manual scrapes via existing DateRangeScraper and manage user access. Settings tab hidden from non-admins.

**Tech Stack:** Flask API, SQLAlchemy, React + Ant Design, existing DateRangeScraper

---

## Task 1: Add Role Column to User Model

**Files:**
- Modify: `database/models.py` (User class, ~line 205)

**Step 1: Add role column to User model**

In `database/models.py`, update the User class:

```python
class User(Base):
    """Users authenticated via Google OAuth."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(255))
    avatar_url = Column(Text)
    role = Column(String(20), nullable=False, default='user')  # 'admin' or 'user'
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_login_at = Column(TIMESTAMP)

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}')>"
```

**Step 2: Run database migration**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';
"
```

Expected: `ALTER TABLE` success message

**Step 3: Verify column exists**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d users"
```

Expected: `role` column appears in table schema

**Step 4: Commit**

```bash
git add database/models.py
git commit -m "feat: add role column to User model"
```

---

## Task 2: Add Admin Seeding on App Startup

**Files:**
- Modify: `web_app/app.py`

**Step 1: Add admin seeding function**

In `web_app/app.py`, add after the imports:

```python
import os
from database.db_config import Session
from database.models import User
```

Add this function before `create_app()`:

```python
def seed_admin_user():
    """Ensure ADMIN_EMAIL user exists with admin role."""
    admin_email = os.environ.get('ADMIN_EMAIL')
    if not admin_email:
        return

    session = Session()
    try:
        user = session.query(User).filter_by(email=admin_email).first()
        if not user:
            user = User(email=admin_email, role='admin')
            session.add(user)
            session.commit()
            print(f"Created admin user: {admin_email}")
        elif user.role != 'admin':
            user.role = 'admin'
            session.commit()
            print(f"Updated user to admin: {admin_email}")
    finally:
        session.close()
```

**Step 2: Call seed function in create_app()**

In `create_app()`, add after registering blueprints (before `return app`):

```python
    # Seed admin user from environment
    seed_admin_user()

    return app
```

**Step 3: Add ADMIN_EMAIL to .env**

```bash
echo "ADMIN_EMAIL=your-email@gmail.com" >> .env
```

Replace `your-email@gmail.com` with actual admin email.

**Step 4: Test admin seeding**

```bash
source venv/bin/activate
export PYTHONPATH=$(pwd)
export ADMIN_EMAIL=test-admin@example.com
python -c "from web_app.app import create_app; create_app()"
```

Expected: "Created admin user: test-admin@example.com" (or "Updated" if exists)

**Step 5: Verify in database**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT email, role FROM users WHERE role='admin';"
```

Expected: Admin user(s) listed

**Step 6: Commit**

```bash
git add web_app/app.py
git commit -m "feat: add admin user seeding on app startup"
```

---

## Task 3: Update Auth to Check Whitelist

**Files:**
- Modify: `web_app/api/routes.py`

**Step 1: Update /api/auth/me endpoint**

Replace the existing `/api/auth/me` endpoint with whitelist checking:

```python
@api_bp.route('/auth/me')
def get_current_user():
    """Get current authenticated user - requires user to be in whitelist."""
    if not google.authorized:
        return jsonify({'authenticated': False}), 401

    user_info = get_google_user_info()
    if not user_info:
        return jsonify({'authenticated': False, 'error': 'Failed to get user info'}), 401

    email = user_info.get('email')

    session = Session()
    try:
        # Check if user exists in whitelist
        user = session.query(User).filter_by(email=email).first()

        if not user:
            # User not in whitelist - reject
            return jsonify({
                'authenticated': False,
                'error': 'Not authorized. Contact admin to request access.'
            }), 403

        # Update user info from Google
        user.display_name = user_info.get('name', user.display_name)
        user.avatar_url = user_info.get('picture', user.avatar_url)
        user.last_login_at = func.current_timestamp()
        session.commit()

        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'avatar_url': user.avatar_url,
                'role': user.role
            }
        })
    finally:
        session.close()
```

**Step 2: Add func import if missing**

At top of `routes.py`, ensure:

```python
from sqlalchemy import func
```

**Step 3: Commit**

```bash
git add web_app/api/routes.py
git commit -m "feat: add whitelist check to auth endpoint"
```

---

## Task 4: Create Admin API Endpoints

**Files:**
- Create: `web_app/api/admin.py`
- Modify: `web_app/app.py` (register blueprint)

**Step 1: Create admin.py with user management endpoints**

Create `web_app/api/admin.py`:

```python
"""Admin API endpoints for user management and manual scraping."""

from flask import Blueprint, jsonify, request
from flask_dance.contrib.google import google
from sqlalchemy import func

from database.db_config import Session
from database.models import User
from web_app.auth.google import get_google_user_info

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def get_current_user_role():
    """Get the role of the currently authenticated user."""
    if not google.authorized:
        return None

    user_info = get_google_user_info()
    if not user_info:
        return None

    session = Session()
    try:
        user = session.query(User).filter_by(email=user_info.get('email')).first()
        return user.role if user else None
    finally:
        session.close()


def require_admin(f):
    """Decorator to require admin role for endpoint."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        role = get_current_user_role()
        if role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    """List all users."""
    session = Session()
    try:
        users = session.query(User).order_by(User.email).all()
        return jsonify([
            {
                'id': u.id,
                'email': u.email,
                'role': u.role
            }
            for u in users
        ])
    finally:
        session.close()


@admin_bp.route('/users', methods=['POST'])
@require_admin
def add_user():
    """Add a new user to the whitelist."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    role = data.get('role', 'user')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if role not in ('admin', 'user'):
        return jsonify({'error': 'Role must be admin or user'}), 400

    session = Session()
    try:
        # Check if user already exists
        existing = session.query(User).filter_by(email=email).first()
        if existing:
            return jsonify({'error': 'User already exists'}), 409

        user = User(email=email, role=role)
        session.add(user)
        session.commit()

        return jsonify({
            'id': user.id,
            'email': user.email,
            'role': user.role
        }), 201
    finally:
        session.close()


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@require_admin
def update_user(user_id):
    """Update a user's role."""
    data = request.get_json()
    role = data.get('role')

    if role not in ('admin', 'user'):
        return jsonify({'error': 'Role must be admin or user'}), 400

    # Get current user to prevent self-modification
    current_user_info = get_google_user_info()

    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prevent changing own role
        if current_user_info and user.email == current_user_info.get('email'):
            return jsonify({'error': 'Cannot change your own role'}), 400

        user.role = role
        session.commit()

        return jsonify({
            'id': user.id,
            'email': user.email,
            'role': user.role
        })
    finally:
        session.close()


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    """Remove a user from the whitelist."""
    # Get current user to prevent self-deletion
    current_user_info = get_google_user_info()

    session = Session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prevent deleting self
        if current_user_info and user.email == current_user_info.get('email'):
            return jsonify({'error': 'Cannot delete yourself'}), 400

        session.delete(user)
        session.commit()

        return jsonify({'success': True})
    finally:
        session.close()
```

**Step 2: Register admin blueprint in app.py**

In `web_app/app.py`, add import:

```python
from web_app.api.admin import admin_bp
```

In `create_app()`, add after other blueprint registrations:

```python
    app.register_blueprint(admin_bp)
```

**Step 3: Commit**

```bash
git add web_app/api/admin.py web_app/app.py
git commit -m "feat: add admin API endpoints for user management"
```

---

## Task 5: Add Manual Scrape Endpoint

**Files:**
- Modify: `web_app/api/admin.py`

**Step 1: Add scrape endpoint to admin.py**

Add at the end of `web_app/api/admin.py`:

```python
@admin_bp.route('/scrape', methods=['POST'])
@require_admin
def run_manual_scrape():
    """Trigger a manual scrape with custom parameters."""
    data = request.get_json() or {}

    start_date = data.get('start_date')
    end_date = data.get('end_date')
    counties = data.get('counties')  # Optional list
    party_name = data.get('party_name')  # Optional string

    # Validate required fields
    if not start_date or not end_date:
        return jsonify({'error': 'start_date and end_date are required'}), 400

    # Validate date format
    import re
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(date_pattern, start_date) or not re.match(date_pattern, end_date):
        return jsonify({'error': 'Dates must be in YYYY-MM-DD format'}), 400

    # Validate counties if provided
    valid_counties = ['WAKE', 'DURHAM', 'HARNETT', 'LEE', 'ORANGE', 'CHATHAM']
    if counties:
        invalid = [c for c in counties if c.upper() not in valid_counties]
        if invalid:
            return jsonify({'error': f'Invalid counties: {invalid}'}), 400
        counties = [c.upper() for c in counties]

    try:
        from scraper.date_range_scrape import DateRangeScraper

        scraper = DateRangeScraper(
            start_date=start_date,
            end_date=end_date,
            counties=counties,
            skip_existing=True
        )

        # If party_name provided, set it on scraper
        if party_name:
            scraper.party_name = party_name

        result = scraper.run()

        return jsonify({
            'status': result.get('status', 'unknown'),
            'cases_processed': result.get('cases_processed', 0),
            'cases_found': result.get('cases_found', 0),
            'error': result.get('error')
        })
    except Exception as e:
        return jsonify({
            'status': 'failed',
            'error': str(e)
        }), 500
```

**Step 2: Commit**

```bash
git add web_app/api/admin.py
git commit -m "feat: add manual scrape endpoint for admin"
```

---

## Task 6: Update DateRangeScraper to Support Party Name

**Files:**
- Modify: `scraper/date_range_scrape.py`
- Modify: `scraper/portal_interactions.py`

**Step 1: Check if party_name support exists**

First, check if `fill_search_form` already accepts party_name:

```bash
grep -n "party_name" scraper/portal_interactions.py
```

**Step 2: Add party_name to DateRangeScraper.__init__**

In `scraper/date_range_scrape.py`, update `__init__`:

```python
def __init__(self, start_date, end_date, counties=None, test_mode=False, limit=None, skip_existing=True, party_name=None):
    """
    Args:
        start_date: Start date (YYYY-MM-DD string)
        end_date: End date (YYYY-MM-DD string)
        counties: List of county names (default: all 6 target counties)
        test_mode: If True, limit scraping for testing
        limit: Maximum number of cases to process (for testing)
        skip_existing: If True, skip cases already in DB (default: True)
        party_name: Optional party name to filter search (default: None)
    """
    self.start_date = start_date
    self.end_date = end_date
    self.counties = counties or TARGET_COUNTIES
    self.test_mode = test_mode
    self.limit = limit
    self.skip_existing = skip_existing
    self.party_name = party_name
```

**Step 3: Pass party_name to fill_search_form**

In `_scrape_cases` method, find the call to `fill_search_form` and update it to pass `party_name`:

```python
fill_search_form(page, self.start_date, self.end_date, self.counties, party_name=self.party_name)
```

**Step 4: Update fill_search_form in portal_interactions.py**

In `scraper/portal_interactions.py`, update `fill_search_form` to accept and use `party_name`:

```python
def fill_search_form(page, start_date, end_date, counties, party_name=None):
    """Fill the advanced search form with date range, counties, and optional party name."""
    # ... existing code ...

    # Add party name if provided
    if party_name:
        party_input = page.locator('input[name="partyName"]')  # Adjust selector as needed
        if party_input.is_visible():
            party_input.fill(party_name)
```

Note: The exact selector for party name field needs to be verified against the portal HTML.

**Step 5: Commit**

```bash
git add scraper/date_range_scrape.py scraper/portal_interactions.py
git commit -m "feat: add party_name parameter to scraper"
```

---

## Task 7: Update Frontend AppLayout for Admin Check

**Files:**
- Modify: `frontend/src/components/AppLayout.jsx`

**Step 1: Update AppLayout to conditionally show Settings**

In `frontend/src/components/AppLayout.jsx`, the user state likely comes from an auth context or API call. Update the menu items to check for admin role:

Replace the menu items array with conditional logic:

```jsx
// In the component, after getting user data
const menuItems = [
  { key: '/', label: <Link to="/">Dashboard</Link> },
  { key: '/cases', label: <Link to="/cases">All Cases</Link> },
  {
    key: '/review',
    label: (
      <Link to="/review">
        Review Queue
        {pendingCount > 0 && (
          <Badge count={pendingCount} size="small" style={{ marginLeft: 8 }} />
        )}
      </Link>
    )
  },
  { key: '/daily-scrape', label: <Link to="/daily-scrape">Daily Scrapes</Link> },
  // Only show Settings for admins
  ...(user?.role === 'admin' ? [{ key: '/settings', label: <Link to="/settings">Settings</Link> }] : [])
];
```

**Step 2: Pass user data to AppLayout**

If not already available, fetch user role from `/api/auth/me` and include it in state.

**Step 3: Commit**

```bash
git add frontend/src/components/AppLayout.jsx
git commit -m "feat: conditionally show Settings tab for admins only"
```

---

## Task 8: Implement Settings Page - Manual Scrape Section

**Files:**
- Modify: `frontend/src/pages/Settings.jsx`

**Step 1: Create Manual Scrape section**

Replace `frontend/src/pages/Settings.jsx` with:

```jsx
import React, { useState, useEffect } from 'react';
import {
  Card,
  DatePicker,
  Checkbox,
  Input,
  Button,
  message,
  Space,
  Typography,
  Row,
  Col,
  Divider,
  Table,
  Modal,
  Form,
  Select,
  Popconfirm,
  Tag
} from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const ALL_COUNTIES = ['WAKE', 'DURHAM', 'HARNETT', 'LEE', 'ORANGE', 'CHATHAM'];

export default function Settings() {
  // Manual Scrape State
  const [dateRange, setDateRange] = useState([null, null]);
  const [selectedCounties, setSelectedCounties] = useState(ALL_COUNTIES);
  const [partyName, setPartyName] = useState('');
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [scrapeResult, setScrapeResult] = useState(null);

  // User Management State
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [addForm] = Form.useForm();

  // Fetch users on mount
  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setUsersLoading(true);
    try {
      const res = await fetch('/api/admin/users', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
      }
    } catch (err) {
      message.error('Failed to load users');
    } finally {
      setUsersLoading(false);
    }
  };

  // County selection handlers
  const handleSelectAll = () => setSelectedCounties(ALL_COUNTIES);
  const handleClearAll = () => setSelectedCounties([]);
  const handleCountyChange = (county, checked) => {
    if (checked) {
      setSelectedCounties([...selectedCounties, county]);
    } else {
      setSelectedCounties(selectedCounties.filter(c => c !== county));
    }
  };

  // Manual scrape handler
  const handleRunScrape = async () => {
    if (!dateRange[0] || !dateRange[1]) {
      message.error('Please select a date range');
      return;
    }
    if (selectedCounties.length === 0) {
      message.error('Please select at least one county');
      return;
    }

    setScrapeLoading(true);
    setScrapeResult(null);

    try {
      const res = await fetch('/api/admin/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          start_date: dateRange[0].format('YYYY-MM-DD'),
          end_date: dateRange[1].format('YYYY-MM-DD'),
          counties: selectedCounties,
          party_name: partyName || undefined
        })
      });

      const data = await res.json();
      setScrapeResult(data);

      if (data.status === 'success') {
        message.success(`Scrape complete: ${data.cases_processed} cases processed`);
      } else {
        message.error(data.error || 'Scrape failed');
      }
    } catch (err) {
      message.error('Failed to run scrape');
      setScrapeResult({ status: 'failed', error: err.message });
    } finally {
      setScrapeLoading(false);
    }
  };

  // User management handlers
  const handleAddUser = async (values) => {
    try {
      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(values)
      });

      if (res.ok) {
        message.success('User added');
        setAddModalVisible(false);
        addForm.resetFields();
        fetchUsers();
      } else {
        const data = await res.json();
        message.error(data.error || 'Failed to add user');
      }
    } catch (err) {
      message.error('Failed to add user');
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ role: newRole })
      });

      if (res.ok) {
        message.success('Role updated');
        fetchUsers();
      } else {
        const data = await res.json();
        message.error(data.error || 'Failed to update role');
      }
    } catch (err) {
      message.error('Failed to update role');
    }
  };

  const handleDeleteUser = async (userId) => {
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (res.ok) {
        message.success('User removed');
        fetchUsers();
      } else {
        const data = await res.json();
        message.error(data.error || 'Failed to remove user');
      }
    } catch (err) {
      message.error('Failed to remove user');
    }
  };

  const userColumns = [
    { title: 'Email', dataIndex: 'email', key: 'email' },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role, record) => (
        <Select
          value={role}
          onChange={(value) => handleRoleChange(record.id, value)}
          style={{ width: 100 }}
          options={[
            { value: 'admin', label: 'Admin' },
            { value: 'user', label: 'User' }
          ]}
        />
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Popconfirm
          title="Remove this user?"
          onConfirm={() => handleDeleteUser(record.id)}
          okText="Yes"
          cancelText="No"
        >
          <Button type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      )
    }
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Settings</Title>

      {/* Manual Scrape Section */}
      <Card title="Manual Scrape" style={{ marginBottom: 24 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* Date Range */}
          <div>
            <Text strong>Date Range:</Text>
            <div style={{ marginTop: 8 }}>
              <RangePicker
                value={dateRange}
                onChange={setDateRange}
                format="YYYY-MM-DD"
              />
            </div>
          </div>

          {/* Counties */}
          <div>
            <Text strong>Counties:</Text>
            <div style={{ marginTop: 8, marginBottom: 8 }}>
              <Space>
                <Button size="small" onClick={handleSelectAll}>Select All</Button>
                <Button size="small" onClick={handleClearAll}>Clear All</Button>
              </Space>
            </div>
            <Row gutter={[16, 8]}>
              {ALL_COUNTIES.map(county => (
                <Col span={8} key={county}>
                  <Checkbox
                    checked={selectedCounties.includes(county)}
                    onChange={(e) => handleCountyChange(county, e.target.checked)}
                  >
                    {county.charAt(0) + county.slice(1).toLowerCase()}
                  </Checkbox>
                </Col>
              ))}
            </Row>
          </div>

          {/* Party Name */}
          <div>
            <Text strong>Party Name:</Text>
            <Text type="secondary" style={{ marginLeft: 8 }}>(optional)</Text>
            <div style={{ marginTop: 8 }}>
              <Input
                placeholder="Enter party name to search"
                value={partyName}
                onChange={(e) => setPartyName(e.target.value)}
                style={{ maxWidth: 400 }}
              />
            </div>
          </div>

          {/* Run Button */}
          <Button
            type="primary"
            onClick={handleRunScrape}
            loading={scrapeLoading}
            disabled={scrapeLoading}
          >
            {scrapeLoading ? 'Running Scrape...' : 'Run Scrape'}
          </Button>

          {/* Results */}
          {scrapeResult && (
            <div style={{ marginTop: 16, padding: 16, background: scrapeResult.status === 'success' ? '#f6ffed' : '#fff2f0', borderRadius: 4 }}>
              <Text strong>Result: </Text>
              <Tag color={scrapeResult.status === 'success' ? 'green' : 'red'}>
                {scrapeResult.status}
              </Tag>
              {scrapeResult.cases_processed !== undefined && (
                <Text>Cases processed: {scrapeResult.cases_processed}</Text>
              )}
              {scrapeResult.error && (
                <div style={{ marginTop: 8 }}>
                  <Text type="danger">{scrapeResult.error}</Text>
                </div>
              )}
            </div>
          )}
        </Space>
      </Card>

      {/* User Management Section */}
      <Card
        title="User Management"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddModalVisible(true)}
          >
            Add User
          </Button>
        }
      >
        <Table
          dataSource={users}
          columns={userColumns}
          rowKey="id"
          loading={usersLoading}
          pagination={false}
        />
      </Card>

      {/* Add User Modal */}
      <Modal
        title="Add User"
        open={addModalVisible}
        onCancel={() => setAddModalVisible(false)}
        footer={null}
      >
        <Form
          form={addForm}
          onFinish={handleAddUser}
          layout="vertical"
          initialValues={{ role: 'user' }}
        >
          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: 'Please enter email' },
              { type: 'email', message: 'Please enter a valid email' }
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>
          <Form.Item
            name="role"
            label="Role"
          >
            <Select
              options={[
                { value: 'user', label: 'User' },
                { value: 'admin', label: 'Admin' }
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">Add User</Button>
              <Button onClick={() => setAddModalVisible(false)}>Cancel</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Settings.jsx
git commit -m "feat: implement Settings page with Manual Scrape and User Management"
```

---

## Task 9: Test End-to-End

**Step 1: Start backend server**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/settings-tab
source venv/bin/activate
export PYTHONPATH=$(pwd)
export ADMIN_EMAIL=your-email@gmail.com
sudo service postgresql start
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(port=5001)"
```

**Step 2: Start frontend dev server**

In another terminal:

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/settings-tab/frontend
npm run dev -- --host
```

**Step 3: Manual testing checklist**

1. [ ] Login via Google OAuth
2. [ ] Verify Settings tab appears (as admin)
3. [ ] User Management: Add a test user
4. [ ] User Management: Change user role
5. [ ] User Management: Delete test user
6. [ ] Manual Scrape: Select date range
7. [ ] Manual Scrape: Toggle counties
8. [ ] Manual Scrape: Enter party name
9. [ ] Manual Scrape: Run scrape and see results

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify Settings tab functionality"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add role column to User model | `database/models.py` |
| 2 | Add admin seeding on startup | `web_app/app.py` |
| 3 | Update auth whitelist check | `web_app/api/routes.py` |
| 4 | Create admin API endpoints | `web_app/api/admin.py`, `web_app/app.py` |
| 5 | Add manual scrape endpoint | `web_app/api/admin.py` |
| 6 | Update scraper for party_name | `scraper/date_range_scrape.py`, `scraper/portal_interactions.py` |
| 7 | Conditionally show Settings tab | `frontend/src/components/AppLayout.jsx` |
| 8 | Implement Settings page | `frontend/src/pages/Settings.jsx` |
| 9 | End-to-end testing | - |
