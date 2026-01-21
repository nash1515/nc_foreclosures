# CLAUDE.md

NC Foreclosures - Foreclosure tracking system for 6 NC counties with upset bid opportunity detection.

**Repo:** https://github.com/nash1515/nc_foreclosures | **Branch:** main

## Subagent-First Architecture

**ALWAYS use subagents (Task tool) for all work.** The terminal window is the **orchestrator** - it thinks, plans, and delegates. Subagents do the actual work.

**Why:** Maximum context window conservation. Direct tool calls consume context rapidly. Subagents execute in isolation and return only results.

**Rules:**
1. **Never run Bash/Read/Edit directly** for multi-step tasks - spawn a subagent
2. **Never explore code directly** - use `subagent_type=Explore`
3. **Never debug directly** - use `subagent_type=general-purpose` with clear instructions
4. **Orchestrator role:** Plan → Delegate → Synthesize results → Report to user
5. **Exception:** Simple single-command operations (starting servers, quick status checks)

## Quick Start

```bash
source venv/bin/activate
export PYTHONPATH=$(pwd)
sudo service postgresql start

# Start dev servers (run in background)
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(host='0.0.0.0', port=5001)" &
cd frontend && npm run dev -- --host &
```

- Frontend: http://localhost:5173 (or http://desktop-aoffice.tail7dda89.ts.net:5173 via Tailscale)
- API: http://localhost:5001 (or http://desktop-aoffice.tail7dda89.ts.net:5001 via Tailscale)

## Current Status

- **2,254 cases** across 6 counties (Wake, Durham, Harnett, Lee, Orange, Chatham)
- **Active upset_bid cases:** 39
- **Scheduler:** 5 AM Mon-Fri + catch-up logic on startup
- **All 6 counties** have RE enrichment complete
- **Deed Enrichment:** 90% extraction rate (35/39 upset_bid cases)
- **Grace Period Monitoring:** 5-day window for closed_sold cases

### Recent Changes (Session 33 - Jan 21)
- **Est. Rehab Cost field** - Added to Bid Information tile below Est. Sale Price. Currency input with auto-save.
- **Profit calculation updated** - Now: `Est. Sale Price - Our Max Bid - Est. Rehab Cost`
- **Case Detail header redesign** - Property address is now the prominent header; removed case style/type title

### Previous Changes (Session 32 - Jan 20)
- Resale bid extraction fix - added sale_date filtering to event search
- Task 9: Weekly closed_sold scan (Fridays) for set-aside events
- Tailscale partner access documented

### Session 31 (Jan 19)
- **Chronology audit - 4 bugs fixed** - Bid amounts, case status, and related data now respect chronological order
- **Interest validation race condition fix** - Frontend sends current form values with interest status change

### Session 30 (Jan 16)
- Dashboard interest status filter with URL persistence
- Deed URL fixes for Logan Systems counties (Lee, Chatham)
- Dashboard county tab persistence

*Full session history: [docs/SESSION_HISTORY.md](docs/SESSION_HISTORY.md)*

## Classifications

| Status | Description |
|--------|-------------|
| upcoming | Foreclosure initiated, no sale yet |
| upset_bid | Sale occurred, within 10-day bid period |
| blocked | Bankruptcy/stay in effect |
| closed_sold | Past upset period |
| closed_dismissed | Case dismissed |

## Key Commands

```bash
# Daily scrape (manual)
./scripts/run_daily.sh

# Scheduler control
./scripts/scheduler_control.sh status|start|stop|logs

# Monitor specific cases
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upset_bid

# Batch scraping
PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
  --start 2024-01-01 --end 2024-12-31 --chunk monthly --workers 3

# Database
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost
```

## Architecture

### Modules
- `scraper/` - Playwright scraper with CAPTCHA solving (CapSolver)
- `extraction/` - Regex extraction + classification from OCR text
- `scheduler/` - Daily scrape automation (5 AM Mon-Fri)
- `web_app/` - Flask API with Google OAuth
- `frontend/` - React + Vite + Ant Design
- `ocr/` - PDF text extraction (Tesseract + Claude Vision fallback)
- `analysis/` - Claude AI analysis
- `enrichments/` - County RE enrichment (all 6 counties) + Deed URLs

### Key Files
- `scraper/daily_scrape.py` - Orchestrates daily tasks
- `scraper/case_monitor.py` - Monitors existing cases via direct URLs
- `extraction/classifier.py` - Case status classification
- `extraction/extractor.py` - Regex extraction + Claude Vision fallback
- `common/business_days.py` - NC court holiday calendar

### Database Tables
`cases`, `case_events`, `parties`, `hearings`, `documents`, `scrape_logs`, `scrape_log_tasks`, `scheduler_config`, `users`, `case_analyses`, `enrichments`

## Critical Design Decisions

1. **Deadlines from events ONLY** - PDF OCR unreliable for handwritten dates. Use `event_date + 10 business days`
2. **NC G.S. 45-21.27** - If 10th day falls on weekend/holiday, extends to next business day
3. **PDF extraction** - Only used for bid amounts, NOT deadlines
4. **Headless=False** - Angular pages fail in headless mode
5. **Documents linked to events** - `documents.event_id` foreign key ties PDFs to case_events
6. **Event descriptions authoritative** - For bid amounts, event text takes precedence over OCR

## Environment Variables (.env)
`DATABASE_URL`, `CAPSOLVER_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FLASK_SECRET_KEY`, `ADMIN_EMAIL`, `AUTH_DISABLED`

## Next Priorities
1. PropWire enrichment (next quicklink)

## Session Commands
- **"Wrap up session"** - Update CLAUDE.md + commit/push + review todos + give handoff
- **"Update docs"** - Update CLAUDE.md + commit/push only
- **"Continue NC Foreclosures"** - Start new session (reads CLAUDE.md automatically)

## Session Handoff Format

```
NC Foreclosures - [Date]
Last: [1-line summary]
Status: [any changes]
Next: [immediate priority]
```

---
*Full session history: [docs/SESSION_HISTORY.md](docs/SESSION_HISTORY.md)*
