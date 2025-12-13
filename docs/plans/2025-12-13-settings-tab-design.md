# Settings Tab Design

**Date:** 2025-12-13
**Status:** Approved

## Overview

Add a Settings tab to the frontend with two sections:
1. Manual Scrape - UI to trigger scrapes with custom parameters
2. User Management - Add/remove users, assign roles

## Requirements

### User Management
- **Role-based access:** Admin and User roles
- **Admin capabilities:** Manage users, run manual scrapes, access scheduler settings
- **User capabilities:** View data, manage their watchlist
- **Whitelist model:** Users must be added by email before they can log in
- **Bootstrap:** `ADMIN_EMAIL` environment variable seeds first admin on startup

### Manual Scrape
- Date range picker (start/end dates)
- County selection: Multi-select checkboxes with Select All/Clear All (default: all 6)
- Party Name search field (optional, free-text passed to portal)
- Hardcoded defaults: Special Proceedings + Pending (matches existing scraper)
- Uses existing `DateRangeScraper` class - no scraper changes needed
- Synchronous execution (matches current DailyScrape pattern)

### Access Control
- Settings tab only visible to Admin users
- Non-admins accessing `/settings` redirect to Dashboard

## Database Changes

### Add role column to users table
```sql
ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user';
-- Values: 'admin', 'user'
```

### Migration script
```sql
ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user';
UPDATE users SET role = 'admin' WHERE email = '<ADMIN_EMAIL from env>';
```

## API Endpoints

### User Management (admin only)

```
GET  /api/admin/users
Response: [{ "id": 1, "email": "user@example.com", "role": "admin" }, ...]

POST /api/admin/users
Body: { "email": "user@example.com", "role": "user" }
Response: { "id": 2, "email": "user@example.com", "role": "user" }

PUT  /api/admin/users/<id>
Body: { "role": "admin" }
Response: { "id": 2, "email": "user@example.com", "role": "admin" }

DELETE /api/admin/users/<id>
Response: { "success": true }
```

### Manual Scrape (admin only)

```
POST /api/admin/scrape
Body: {
  "start_date": "2025-01-01",      // required, YYYY-MM-DD
  "end_date": "2025-01-31",        // required, YYYY-MM-DD
  "counties": ["WAKE", "DURHAM"],  // optional, defaults to all 6
  "party_name": "Smith"            // optional
}
Response: {
  "status": "success",
  "cases_processed": 15,
  "cases_found": 20
}
```

## Auth Changes

### Login flow update
1. User authenticates via Google OAuth
2. Check if email exists in `users` table
3. If not in whitelist → reject with "Not authorized" message
4. If exists → allow login, update `last_login_at`

### Admin seeding on startup
1. Read `ADMIN_EMAIL` from environment
2. If user with that email doesn't exist → create with `role='admin'`
3. If user exists but not admin → update to `role='admin'`

## Frontend UI

```
┌─────────────────────────────────────────────────────┐
│ Settings                                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─ Manual Scrape ────────────────────────────────┐  │
│ │                                                │  │
│ │  Date Range:  [Start Date] → [End Date]        │  │
│ │                                                │  │
│ │  Counties:    [✓] Select All  [ ] Clear All    │  │
│ │               [✓] Wake    [✓] Durham           │  │
│ │               [✓] Harnett [✓] Lee              │  │
│ │               [✓] Orange  [✓] Chatham          │  │
│ │                                                │  │
│ │  Party Name:  [________________________]       │  │
│ │               (optional)                       │  │
│ │                                                │  │
│ │  [Run Scrape]                                  │  │
│ │                                                │  │
│ └────────────────────────────────────────────────┘  │
│                                                     │
│ ┌─ User Management ──────────────────────────────┐  │
│ │                                                │  │
│ │  [Add User] button                             │  │
│ │                                                │  │
│ │  ┌──────────────────────────────────────────┐  │  │
│ │  │ Email              │ Role   │ Actions    │  │  │
│ │  ├──────────────────────────────────────────┤  │  │
│ │  │ admin@example.com  │ Admin  │ -          │  │  │
│ │  │ user@example.com   │ User   │ [▼] [X]    │  │  │
│ │  └──────────────────────────────────────────┘  │  │
│ └────────────────────────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### User Management Behavior
- **Add User:** Modal with email input + role dropdown (default: User)
- **Role dropdown [▼]:** Toggle between Admin/User
- **[X] button:** Confirm modal → remove user
- **Constraints:** Cannot remove yourself or change your own role

### Manual Scrape Behavior
- **Run Scrape:** Disables button, shows spinner
- **On complete:** Display results (cases found/processed) or error message

### Navigation
- Settings tab only visible to Admin users in sidebar
- Non-admins trying to access `/settings` → redirect to Dashboard

## Implementation Files

### Backend (Python/Flask)

| File | Changes |
|------|---------|
| `database/models.py` | Add `role` column to User model |
| `web_app/app.py` | Add admin seeding on startup from `ADMIN_EMAIL` |
| `web_app/api/admin.py` | **New file** - user management + manual scrape endpoints |
| `web_app/auth/google.py` | Check whitelist on login, reject if not in users table |

### Frontend (React)

| File | Changes |
|------|---------|
| `frontend/src/pages/Settings.jsx` | Replace placeholder with full implementation |
| `frontend/src/components/AppLayout.jsx` | Conditionally show Settings tab for admins only |

### Environment

| Variable | Purpose |
|----------|---------|
| `ADMIN_EMAIL` | Email address to seed as first admin user |

## Summary

- **1 new backend file** (`admin.py`)
- **3 backend file edits** (`models.py`, `app.py`, `google.py`)
- **2 frontend file edits** (`Settings.jsx`, `AppLayout.jsx`)
- **1 DB migration** (add role column)
- **1 env variable** (`ADMIN_EMAIL`)
