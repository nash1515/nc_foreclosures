# CLAUDE.md

NC Foreclosures - Foreclosure tracking system for 6 NC counties with upset bid opportunity detection.

**Repo:** https://github.com/nash1515/nc_foreclosures | **Branch:** main

## Quick Start

```bash
source venv/bin/activate
export PYTHONPATH=$(pwd)
sudo service postgresql start

# Start dev servers (run in background)
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(port=5001)" &
cd frontend && npm run dev -- --host &
```

**Always start both servers at session start so user can test UI changes.**
- Frontend: http://localhost:5173
- API: http://localhost:5001

## Current Status (Dec 9, 2025)

- **1,731 cases** across 6 counties (Wake, Durham, Harnett, Lee, Orange, Chatham)
- **17 active upset_bid** cases with deadlines
- **Scheduler running** 5 AM Mon-Fri (3-day lookback on Mondays)
- **Frontend:** React + Flask API (Dashboard with county filtering)
- **Review Queue:** Approve/Reject buttons + Flagged for Re-review section

### Classifications
| Status | Count | Description |
|--------|-------|-------------|
| upcoming | ~1,345 | Foreclosure initiated, no sale |
| upset_bid | ~17 | Sale occurred, within 10-day bid period |
| blocked | ~70 | Bankruptcy/stay in effect |
| closed_sold | ~226 | Past upset period |
| closed_dismissed | ~56 | Case dismissed |

## Key Commands

```bash
# Daily scrape (manual)
./scripts/run_daily.sh

# Scheduler control
./scripts/scheduler_control.sh status|start|stop|logs

# Monitor specific cases
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upset_bid

# Database queries
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost
```

## Architecture

### Modules
- `scraper/` - Playwright scraper with CAPTCHA solving (CapSolver)
- `extraction/` - Regex extraction + classification from OCR text
- `scheduler/` - Daily scrape automation (5 AM Mon-Fri)
- `web_app/` - Flask API with Google OAuth
- `frontend/` - React + Vite + Ant Design
- `ocr/` - PDF text extraction (Tesseract)
- `analysis/` - Claude AI analysis (haiku model)

### Key Files
- `scraper/case_monitor.py` - Monitors existing cases via direct URLs (no CAPTCHA)
- `scraper/daily_scrape.py` - Orchestrates daily tasks (3-day lookback on Mondays)
- `scraper/page_parser.py` - Day-1 detection indicators + exclusions
- `extraction/classifier.py` - Case status classification
- `common/business_days.py` - NC court holiday calendar for deadline calculation
- `scripts/reevaluate_skipped.py` - Re-check skipped cases against updated indicators

### Database Tables
`cases`, `case_events`, `parties`, `hearings`, `documents`, `scrape_logs`, `scheduler_config`, `users`

## Critical Design Decisions

1. **Deadlines from events ONLY** - PDF OCR unreliable for handwritten dates. Use `event_date + 10 business days`
2. **NC G.S. 45-21.27** - If 10th day falls on weekend/holiday, extends to next business day
3. **PDF extraction** - Only used for bid amounts, NOT deadlines
4. **Headless=False** - Angular pages fail in headless mode

## Environment Variables (.env)
`DATABASE_URL`, `CAPSOLVER_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FLASK_SECRET_KEY`

## Frontend Development

```bash
# Create feature worktree
./scripts/dev_worktree.sh create my-feature
cd .worktrees/my-feature/frontend
npm install && npm run dev -- --port 5174
```

## Next Priorities
1. Build Case Detail page
2. Build Case List page with filtering
3. Enrichment module (Zillow, tax records)
4. Analyze closed_sold cases for bidding patterns

## Session Commands
- **"Wrap up session"** - Update CLAUDE.md + commit/push + review todos + give handoff
- **"Update docs"** - Update CLAUDE.md + commit/push only
- **"Continue NC Foreclosures"** - Start new session (reads CLAUDE.md automatically)

## Session Handoff Format

After each session, I'll provide a compact handoff like:
```
NC Foreclosures - [Date]
Last: [1-line summary of what was done]
Status: [any changes to counts/status]
Next: [immediate priority if any]
```

You just need to say "Continue NC Foreclosures" and I'll read this file automatically.

---
*Detailed session history moved to `docs/SESSION_HISTORY.md`*
