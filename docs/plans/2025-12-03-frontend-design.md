# Frontend Design - NC Foreclosures Dashboard

**Created:** December 3, 2025
**Status:** Approved

## Overview

A React-based team dashboard for tracking NC foreclosure cases and coordinating upset bid opportunities.

### Primary Use Case
Team tool for multiple users (partners/investors) to view cases, coordinate bidding strategy, and leave notes.

### Key Decisions
- **Framework:** Vite + React + Ant Design
- **Backend:** Flask REST API (extending existing Python codebase)
- **Auth:** Google OAuth 2.0
- **Hosting:** Local initially, designed for future cloud deployment

---

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌──────────────┐
│  React Frontend │ ───▶ │  Flask API      │ ───▶ │  PostgreSQL  │
│  (Vite + antd)  │      │  /api/*         │      │  (existing)  │
│  Port 5173      │      │  Port 5000      │      │              │
└─────────────────┘      └─────────────────┘      └──────────────┘
```

### Folder Structure

```
nc_foreclosures/
├── frontend/              # NEW - React app
│   ├── src/
│   │   ├── pages/         # Dashboard, CaseList, CaseDetail, Settings
│   │   ├── components/    # Shared UI components
│   │   └── api/           # API client functions
│   ├── package.json
│   └── vite.config.js
├── web_app/               # Flask API (expand existing)
│   ├── api/               # REST endpoints
│   │   ├── cases.py
│   │   ├── watchlist.py
│   │   ├── notes.py
│   │   └── dashboard.py
│   └── auth/              # Google OAuth
│       └── google.py
└── ... (existing modules)
```

---

## Pages & Navigation

### 1. Upset Bid Dashboard (Home - `/`)

Primary landing page showing time-sensitive opportunities.

**Alert Banner (top):**
- Red: Last scheduled scrape failed or missing
- Yellow: Scrape succeeded but 0 new cases (possible portal issue)
- Green/Hidden: Normal operation
- Includes "Run Manual Scrape" and "View Logs" quick actions

**Main Content:**
- Table of active upset bid cases (~24 currently)
- Sorted by deadline (most urgent first)
- Columns: Case Number, Property Address, County, Current Bid, Min Next Bid, Deadline Countdown, Your Bid Ladder (initial/2nd/max)
- Quick filters: County, Deadline (today, this week, all)

### 2. All Cases (`/cases`)

Full searchable/filterable table of all cases.

**Filters:**
- Classification (upcoming, upset_bid, blocked, closed_sold, closed_dismissed)
- County (Wake, Durham, Orange, Chatham, Lee, Harnett)
- Date range (file date)
- Search (address, case number, party name)
- Watchlist only toggle

**Columns:**
- Case Number (link to detail)
- Style
- County
- Classification (color-coded tag)
- File Date
- Watchlist star

**Features:**
- Ant Design Table with built-in sorting, pagination
- Bulk select for future features

### 3. Case Detail (`/cases/:id`)

Full case information and team collaboration.

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Cases          25SP001123-310          ★ Watchlist   │
├─────────────────────────────────────────────────────────────────┤
│ FORECLOSURE OF A DEED OF TRUST - Julie Marie Parks             │
│ Durham County | Filed: 12/02/2025 | Status: Pending            │
│ Classification: [upset_bid]  Deadline: Dec 12 (9 days)         │
├────────────────────────────┬────────────────────────────────────┤
│ PROPERTY                   │ YOUR BID LADDER                    │
│ 123 Main St, Durham NC     │ Initial:  $________               │
│                            │ 2nd Bid:  $________               │
│ [Zillow] [Propwire]        │ Max Bid:  $________               │
│ [County Records] [Deed]    │           [Save]                  │
├────────────────────────────┴────────────────────────────────────┤
│ PARTIES                                                         │
│ • Respondent: Julie Marie Parks                                │
│ • Petitioner: ABC Mortgage Co                                  │
│ • Trustee: Smith Law Firm                                      │
│                                                                │
│ UPSET BIDDERS                                                  │
│ • 12/05/2025: John Doe - $315,000                             │
│ • 12/03/2025: Jane Smith - $304,500 (opening bid)             │
├─────────────────────────────────────────────────────────────────┤
│ EVENTS TIMELINE                                                 │
│ 12/02/2025  Foreclosure Case Initiated                         │
│ 12/01/2025  Notice of Hearing Filed                            │
│ ...                                                            │
├─────────────────────────────────────────────────────────────────┤
│ TEAM NOTES                                                      │
│ ┌─────────────────────────────────────────────────────────────┐│
│ │ John (Dec 3): Drove by property, looks well maintained      ││
│ │ Sarah (Dec 2): Zillow estimate seems high for this area     ││
│ └─────────────────────────────────────────────────────────────┘│
│ [Add a note...                                      ] [Post]    │
└─────────────────────────────────────────────────────────────────┘
```

**Enrichment Links Section:**
- Zillow, Propwire, County Records, Deed
- Auto-generated (logic to be built in future enrichment phase)
- Placeholder UI ready

### 4. Settings (`/settings`)

Admin configuration page.

**Scheduler Section:**
- Current schedule display (e.g., "5:00 AM Mon-Fri")
- Edit time (hour, minute dropdowns)
- Edit days (checkbox for each day)
- Enable/disable toggle
- "Run Manual Scrape" button
- Last run status display

**Scrape History:**
- Table of recent scrapes
- Columns: Date, Status, Cases Found, Duration
- Link to view logs/errors

---

## Database Changes

### New Tables

```sql
-- Users (from Google OAuth)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

-- Watchlist (user's starred cases)
CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, case_id)
);

-- Team notes on cases
CREATE TABLE case_notes (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    note_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Modifications to Existing Tables

```sql
-- Add bid ladder fields to cases table
ALTER TABLE cases ADD COLUMN bid_initial DECIMAL(12, 2);
ALTER TABLE cases ADD COLUMN bid_second DECIMAL(12, 2);
ALTER TABLE cases ADD COLUMN bid_max DECIMAL(12, 2);
ALTER TABLE cases ADD COLUMN bid_updated_by INTEGER REFERENCES users(id);
ALTER TABLE cases ADD COLUMN bid_updated_at TIMESTAMP;
```

---

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/login` | Redirect to Google OAuth |
| GET | `/api/auth/callback` | Handle Google callback, create session |
| GET | `/api/auth/me` | Get current logged-in user |
| POST | `/api/auth/logout` | End session |

### Cases
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cases` | List cases with filters |
| GET | `/api/cases/:id` | Full case detail |
| PATCH | `/api/cases/:id/bid` | Update bid ladder |

### Watchlist
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/watchlist/:case_id` | Add to watchlist |
| DELETE | `/api/watchlist/:case_id` | Remove from watchlist |

### Notes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cases/:id/notes` | Get notes for a case |
| POST | `/api/cases/:id/notes` | Add a note |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/alerts` | Check scrape status, return alerts |
| GET | `/api/dashboard/upset-bids` | Active upset bids with countdown |

### Scheduler (existing)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scheduler/config` | Get scheduler config |
| PUT | `/api/scheduler/config/daily_scrape` | Update schedule |
| POST | `/api/scheduler/config/daily_scrape/toggle` | Enable/disable |
| POST | `/api/scheduler/run/daily_scrape` | Trigger manual run |
| GET | `/api/scheduler/history` | View scrape history |

---

## Implementation Phases

### Phase 1 - Foundation
- Set up Vite + React + Ant Design project in `/frontend`
- Flask API skeleton with CORS support
- Google OAuth login flow
- Basic routing (Dashboard, Cases, Settings pages as shells)

### Phase 2 - Core Features
- All Cases page with Ant Design table (search, filter, sort, pagination)
- Case Detail page with full info display
- Watchlist toggle (star/unstar)
- Database migrations (users, watchlist, case_notes, bid ladder fields)

### Phase 3 - Collaboration Features
- Team notes (add, view with timestamps/authors)
- Bid ladder editing (initial, 2nd, max)
- Upset bidders display in case detail

### Phase 4 - Dashboard & Alerts
- Upset Bid Dashboard as home page (sorted by deadline)
- Scrape alert system (red/yellow/green banners)
- Scheduler settings page (wire up existing API)
- Manual scrape trigger button

### Phase 5 - Polish
- Loading states, error handling, empty states
- Mobile responsiveness
- Enrichment links section (placeholder UI, ready for future logic)

---

## Future Considerations

### Cloud Deployment
- Designed to be deployable to cloud hosting
- Will need: domain, SSL cert, production database
- Options: Railway, Render, DigitalOcean, AWS

### Enrichment Module
- Auto-generate links for: Zillow, Propwire, County Records, Deed
- Logic to be built based on property address/parcel ID
- UI placeholders ready in Phase 5

### Public Access
- Current design supports team access via Google SSO
- Future public-facing features would need additional auth considerations
