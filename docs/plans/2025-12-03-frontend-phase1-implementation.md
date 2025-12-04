# Frontend Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up the React + Flask foundation with Google OAuth authentication and basic page routing.

**Architecture:** Vite + React frontend with Ant Design components communicating with Flask REST API. Google OAuth 2.0 handles authentication via Flask-Dance. Frontend runs on port 5173, API on port 5000 with CORS enabled.

**Tech Stack:** Vite, React 18, React Router, Ant Design 5, Flask, Flask-CORS, Flask-Dance (Google OAuth), SQLAlchemy

---

## Task 1: Create React App with Vite

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/App.css`

**Step 1: Initialize Vite React project**

Run from worktree root:
```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
npm create vite@latest frontend -- --template react
```

Expected: Creates `frontend/` directory with React template

**Step 2: Install dependencies**

```bash
cd frontend
npm install
npm install antd @ant-design/icons react-router-dom axios
```

Expected: Installs React, Ant Design, React Router, Axios

**Step 3: Verify dev server starts**

```bash
npm run dev
```

Expected: Server starts on http://localhost:5173, shows Vite + React page

**Step 4: Commit**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
git add frontend/
git commit -m "feat: initialize React frontend with Vite and Ant Design"
```

---

## Task 2: Configure Vite Proxy for API

**Files:**
- Modify: `frontend/vite.config.js`

**Step 1: Update vite.config.js with API proxy**

Replace contents of `frontend/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
```

**Step 2: Commit**

```bash
git add frontend/vite.config.js
git commit -m "feat: configure Vite proxy for Flask API"
```

---

## Task 3: Create Basic Page Components

**Files:**
- Create: `frontend/src/pages/Dashboard.jsx`
- Create: `frontend/src/pages/CaseList.jsx`
- Create: `frontend/src/pages/CaseDetail.jsx`
- Create: `frontend/src/pages/Settings.jsx`
- Create: `frontend/src/pages/Login.jsx`

**Step 1: Create pages directory and Dashboard page**

Create `frontend/src/pages/Dashboard.jsx`:

```jsx
import { Typography, Alert } from 'antd';

const { Title } = Typography;

function Dashboard() {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Upset Bid Dashboard</Title>
      <Alert
        message="Coming Soon"
        description="Active upset bid cases will appear here, sorted by deadline."
        type="info"
        showIcon
      />
    </div>
  );
}

export default Dashboard;
```

**Step 2: Create CaseList page**

Create `frontend/src/pages/CaseList.jsx`:

```jsx
import { Typography, Alert } from 'antd';

const { Title } = Typography;

function CaseList() {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>All Cases</Title>
      <Alert
        message="Coming Soon"
        description="Searchable table of all 1,724 cases will appear here."
        type="info"
        showIcon
      />
    </div>
  );
}

export default CaseList;
```

**Step 3: Create CaseDetail page**

Create `frontend/src/pages/CaseDetail.jsx`:

```jsx
import { Typography, Alert } from 'antd';
import { useParams } from 'react-router-dom';

const { Title } = Typography;

function CaseDetail() {
  const { id } = useParams();

  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Case Detail: {id}</Title>
      <Alert
        message="Coming Soon"
        description="Full case information, bid ladder, and notes will appear here."
        type="info"
        showIcon
      />
    </div>
  );
}

export default CaseDetail;
```

**Step 4: Create Settings page**

Create `frontend/src/pages/Settings.jsx`:

```jsx
import { Typography, Alert } from 'antd';

const { Title } = Typography;

function Settings() {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Settings</Title>
      <Alert
        message="Coming Soon"
        description="Scheduler configuration will appear here."
        type="info"
        showIcon
      />
    </div>
  );
}

export default Settings;
```

**Step 5: Create Login page**

Create `frontend/src/pages/Login.jsx`:

```jsx
import { Button, Card, Typography, Space } from 'antd';
import { GoogleOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

function Login() {
  const handleGoogleLogin = () => {
    window.location.href = '/api/auth/login';
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: '#f0f2f5'
    }}>
      <Card style={{ width: 400, textAlign: 'center' }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Title level={2}>NC Foreclosures</Title>
          <Text type="secondary">Sign in to access the dashboard</Text>
          <Button
            type="primary"
            icon={<GoogleOutlined />}
            size="large"
            onClick={handleGoogleLogin}
            style={{ width: '100%' }}
          >
            Sign in with Google
          </Button>
        </Space>
      </Card>
    </div>
  );
}

export default Login;
```

**Step 6: Commit**

```bash
git add frontend/src/pages/
git commit -m "feat: add placeholder page components"
```

---

## Task 4: Create App Layout with Navigation

**Files:**
- Create: `frontend/src/components/AppLayout.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/App.css`

**Step 1: Create AppLayout component**

Create `frontend/src/components/AppLayout.jsx`:

```jsx
import { Layout, Menu, Avatar, Dropdown, Space } from 'antd';
import {
  DashboardOutlined,
  FileSearchOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined
} from '@ant-design/icons';
import { Link, Outlet, useLocation } from 'react-router-dom';

const { Header, Content } = Layout;

function AppLayout({ user }) {
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: <Link to="/">Dashboard</Link>,
    },
    {
      key: '/cases',
      icon: <FileSearchOutlined />,
      label: <Link to="/cases">All Cases</Link>,
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">Settings</Link>,
    },
  ];

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Logout',
      onClick: () => {
        window.location.href = '/api/auth/logout';
      },
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div style={{
            color: 'white',
            fontSize: '18px',
            fontWeight: 'bold',
            marginRight: '48px'
          }}>
            NC Foreclosures
          </div>
          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ flex: 1, minWidth: 0 }}
          />
        </div>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar
              src={user?.avatar_url}
              icon={!user?.avatar_url && <UserOutlined />}
            />
            <span style={{ color: 'white' }}>{user?.display_name || 'User'}</span>
          </Space>
        </Dropdown>
      </Header>
      <Content style={{ background: '#f0f2f5' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}

export default AppLayout;
```

**Step 2: Update App.jsx with routing**

Replace `frontend/src/App.jsx`:

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, Spin } from 'antd';
import { useState, useEffect } from 'react';
import AppLayout from './components/AppLayout';
import Dashboard from './pages/Dashboard';
import CaseList from './pages/CaseList';
import CaseDetail from './pages/CaseDetail';
import Settings from './pages/Settings';
import Login from './pages/Login';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is authenticated
    fetch('/api/auth/me')
      .then(res => {
        if (res.ok) return res.json();
        throw new Error('Not authenticated');
      })
      .then(data => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        setUser(null);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh'
      }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1890ff',
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={
            user ? <Navigate to="/" replace /> : <Login />
          } />
          <Route element={
            user ? <AppLayout user={user} /> : <Navigate to="/login" replace />
          }>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cases" element={<CaseList />} />
            <Route path="/cases/:id" element={<CaseDetail />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
```

**Step 3: Update App.css**

Replace `frontend/src/App.css`:

```css
#root {
  width: 100%;
  min-height: 100vh;
}

body {
  margin: 0;
  padding: 0;
}

/* Ant Design overrides */
.ant-layout-header {
  position: sticky;
  top: 0;
  z-index: 1;
}

.ant-menu-horizontal {
  border-bottom: none;
}
```

**Step 4: Verify frontend compiles**

```bash
cd frontend
npm run dev
```

Expected: No compilation errors, app loads (will show login page since no auth yet)

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add app layout with navigation and routing"
```

---

## Task 5: Set Up Flask API Skeleton

**Files:**
- Modify: `web_app/__init__.py`
- Create: `web_app/app.py`
- Create: `web_app/api/__init__.py`
- Create: `web_app/api/routes.py`

**Step 1: Create Flask app factory**

Create `web_app/app.py`:

```python
"""Flask application factory."""

from flask import Flask
from flask_cors import CORS

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS for development
    CORS(app, supports_credentials=True, origins=['http://localhost:5173'])

    # Load configuration
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

    # Register blueprints
    from web_app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Register scheduler API (already built)
    from scheduler.api import scheduler_api
    app.register_blueprint(scheduler_api)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
```

**Step 2: Create API routes blueprint**

Create `web_app/api/__init__.py`:

```python
"""API routes package."""
```

Create `web_app/api/routes.py`:

```python
"""Main API routes."""

from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


@api_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user.

    For now, returns 401 until Google OAuth is set up.
    """
    # TODO: Implement actual auth check
    return jsonify({'error': 'Not authenticated'}), 401


@api_bp.route('/auth/logout', methods=['POST', 'GET'])
def logout():
    """Log out current user."""
    # TODO: Implement actual logout
    return jsonify({'message': 'Logged out'})
```

**Step 3: Update web_app/__init__.py**

Replace `web_app/__init__.py`:

```python
"""Web application package."""

from web_app.app import create_app

__all__ = ['create_app']
```

**Step 4: Test Flask API starts**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app import create_app; app = create_app(); print('App created successfully')"
```

Expected: "App created successfully"

**Step 5: Commit**

```bash
git add web_app/
git commit -m "feat: create Flask API skeleton with CORS"
```

---

## Task 6: Add Google OAuth Authentication

**Files:**
- Create: `web_app/auth/__init__.py`
- Create: `web_app/auth/google.py`
- Modify: `web_app/app.py`
- Modify: `web_app/api/routes.py`
- Modify: `.env.example`

**Step 1: Install Flask-Dance**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
venv/bin/pip install Flask-Dance[sqla]
```

**Step 2: Create auth package**

Create `web_app/auth/__init__.py`:

```python
"""Authentication package."""
```

Create `web_app/auth/google.py`:

```python
"""Google OAuth configuration."""

import os
from flask import redirect, url_for, session, jsonify
from flask_dance.contrib.google import make_google_blueprint, google


def create_google_blueprint():
    """Create Google OAuth blueprint."""
    blueprint = make_google_blueprint(
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        scope=['openid', 'email', 'profile'],
        redirect_url='/api/auth/callback'
    )
    return blueprint


def get_google_user_info():
    """Get user info from Google."""
    if not google.authorized:
        return None

    resp = google.get('/oauth2/v2/userinfo')
    if resp.ok:
        return resp.json()
    return None
```

**Step 3: Update app.py with Google OAuth**

Replace `web_app/app.py`:

```python
"""Flask application factory."""

import os
from flask import Flask, session
from flask_cors import CORS


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS for development
    CORS(app, supports_credentials=True, origins=['http://localhost:5173'])

    # Load configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Google OAuth config
    app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')

    # For development without HTTPS
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    # Register Google OAuth blueprint
    from web_app.auth.google import create_google_blueprint
    google_bp = create_google_blueprint()
    app.register_blueprint(google_bp, url_prefix='/api/auth')

    # Register API routes
    from web_app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Register scheduler API (already built)
    from scheduler.api import scheduler_api
    app.register_blueprint(scheduler_api)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
```

**Step 4: Update API routes with auth endpoints**

Replace `web_app/api/routes.py`:

```python
"""Main API routes."""

from flask import Blueprint, jsonify, redirect, session
from flask_dance.contrib.google import google
from database.connection import get_session
from database.models import User
from datetime import datetime

api_bp = Blueprint('api', __name__)


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


@api_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    # Get user info from Google
    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        return jsonify({'error': 'Failed to get user info'}), 401

    google_info = resp.json()
    email = google_info.get('email')

    # Get or create user in database
    with get_session() as db_session:
        user = db_session.query(User).filter_by(email=email).first()

        if not user:
            user = User(
                email=email,
                display_name=google_info.get('name'),
                avatar_url=google_info.get('picture')
            )
            db_session.add(user)
            db_session.commit()
        else:
            # Update last login
            user.last_login_at = datetime.utcnow()
            user.display_name = google_info.get('name')
            user.avatar_url = google_info.get('picture')
            db_session.commit()

        return jsonify({
            'id': user.id,
            'email': user.email,
            'display_name': user.display_name,
            'avatar_url': user.avatar_url
        })


@api_bp.route('/auth/login', methods=['GET'])
def login():
    """Redirect to Google OAuth."""
    return redirect('/api/auth/google')


@api_bp.route('/auth/callback', methods=['GET'])
def auth_callback():
    """Handle OAuth callback - redirect to frontend."""
    return redirect('http://localhost:5173/')


@api_bp.route('/auth/logout', methods=['POST', 'GET'])
def logout():
    """Log out current user."""
    # Clear Flask-Dance token
    if 'google_oauth_token' in session:
        del session['google_oauth_token']
    return redirect('http://localhost:5173/login')
```

**Step 5: Update .env.example**

Add to `.env.example`:

```
# Google OAuth (get from https://console.cloud.google.com/apis/credentials)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
FLASK_SECRET_KEY=generate-a-random-secret-key
```

**Step 6: Commit**

```bash
git add web_app/ .env.example
git commit -m "feat: add Google OAuth authentication"
```

---

## Task 7: Add User Model to Database

**Files:**
- Modify: `database/models.py`
- Create: `database/migrations/add_users_table.sql`

**Step 1: Add User model**

Add to `database/models.py` after the imports:

```python
class User(Base):
    """Users authenticated via Google OAuth."""

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(255))
    avatar_url = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_login_at = Column(TIMESTAMP)

    def __repr__(self):
        return f"<User(email='{self.email}', display_name='{self.display_name}')>"
```

**Step 2: Create SQL migration**

Create `database/migrations/add_users_table.sql`:

```sql
-- Add users table for Google OAuth authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
```

**Step 3: Run migration**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f database/migrations/add_users_table.sql
```

Expected: CREATE TABLE, CREATE INDEX

**Step 4: Verify table exists**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d users"
```

Expected: Shows users table schema

**Step 5: Commit**

```bash
git add database/
git commit -m "feat: add users table for OAuth authentication"
```

---

## Task 8: Create Run Scripts

**Files:**
- Create: `scripts/run_frontend.sh`
- Create: `scripts/run_api.sh`
- Create: `scripts/run_dev.sh`

**Step 1: Create frontend run script**

Create `scripts/run_frontend.sh`:

```bash
#!/bin/bash
# Run the React frontend dev server

cd "$(dirname "$0")/../frontend"
npm run dev
```

**Step 2: Create API run script**

Create `scripts/run_api.sh`:

```bash
#!/bin/bash
# Run the Flask API server

cd "$(dirname "$0")/.."
export PYTHONPATH=$(pwd)
source venv/bin/activate

# Load .env if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

python web_app/app.py
```

**Step 3: Create combined dev script**

Create `scripts/run_dev.sh`:

```bash
#!/bin/bash
# Run both frontend and API in development mode

cd "$(dirname "$0")/.."

echo "Starting Flask API on port 5000..."
./scripts/run_api.sh &
API_PID=$!

echo "Starting React frontend on port 5173..."
./scripts/run_frontend.sh &
FRONTEND_PID=$!

echo ""
echo "Development servers running:"
echo "  - API: http://localhost:5000"
echo "  - Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for Ctrl+C and cleanup
trap "kill $API_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
```

**Step 4: Make scripts executable**

```bash
chmod +x scripts/run_frontend.sh scripts/run_api.sh scripts/run_dev.sh
```

**Step 5: Commit**

```bash
git add scripts/
git commit -m "feat: add development run scripts"
```

---

## Task 9: Test Full Integration

**Step 1: Ensure PostgreSQL is running**

```bash
echo "ahn" | sudo -S service postgresql status
```

**Step 2: Start API server in background**

```bash
cd /home/ahn/projects/nc_foreclosures/.worktrees/frontend
PYTHONPATH=$(pwd) venv/bin/python web_app/app.py &
```

**Step 3: Test health endpoint**

```bash
curl http://localhost:5000/api/health
```

Expected: `{"status":"healthy"}`

**Step 4: Test auth endpoint (should return 401)**

```bash
curl http://localhost:5000/api/auth/me
```

Expected: `{"error":"Not authenticated"}`

**Step 5: Start frontend**

```bash
cd frontend && npm run dev
```

**Step 6: Verify in browser**

Open http://localhost:5173

Expected: Login page with "Sign in with Google" button appears

**Step 7: Stop servers and commit final state**

```bash
# Kill background processes
pkill -f "python web_app/app.py"

git add -A
git commit -m "feat: complete Phase 1 - React + Flask foundation with Google OAuth"
```

---

## Phase 1 Complete Checklist

- [ ] React app created with Vite
- [ ] Ant Design installed and configured
- [ ] React Router with page shells (Dashboard, CaseList, CaseDetail, Settings, Login)
- [ ] App layout with navigation
- [ ] Flask API with CORS
- [ ] Google OAuth blueprint configured
- [ ] Users table in database
- [ ] Auth endpoints (/api/auth/me, /api/auth/login, /api/auth/logout)
- [ ] Development run scripts
- [ ] Frontend shows login page
- [ ] Protected routes redirect to login

## Next Phase Preview

Phase 2 will implement:
- All Cases page with Ant Design table
- Case Detail page with full info
- Watchlist functionality
- Database tables for watchlist and notes
