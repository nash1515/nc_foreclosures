# CLAUDE.md

NC Foreclosures - Foreclosure tracking system for 6 NC counties with upset bid opportunity detection.

**Repo:** https://github.com/nash1515/nc_foreclosures | **Branch:** main

## ⚠️ CRITICAL: Subagent-First Architecture

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
PYTHONPATH=$(pwd) venv/bin/python -c "from web_app.app import create_app; create_app().run(port=5001)" &
cd frontend && npm run dev -- --host &
```

**Always start both servers at session start so user can test UI changes.**
- Frontend: http://localhost:5173
- API: http://localhost:5001

## Current Status (Dec 11, 2025)

- **1,750 cases** across 6 counties (Wake, Durham, Harnett, Lee, Orange, Chatham)
- **1,075 cases with addresses** (61.4%) / **675 cases missing addresses**
- **25 active upset_bid** cases with deadlines
- **Scheduler running** 5 AM Mon-Fri (3-day lookback on Mondays)
- **Frontend:** React + Flask API (Dashboard with county filtering, improved layout)
- **Review Queue:** Fixed +Add button (JSON encoding), Approve/Reject working

### Recent Session Fixes (Dec 11)
- Fixed double-encoded JSON bug in Review Queue +Add button
- Added SCRA and "petition for sale" as foreclosure indicators
- Implemented priority-based address extraction (searches multiple documents)
- Fixed OCR pipeline to persist extracted text to database
- Rearranged Dashboard layout (filter next to heading, stats at bottom)

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

# Download missing documents
PYTHONPATH=$(pwd) venv/bin/python scripts/download_missing_documents.py

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
- `scripts/download_missing_documents.py` - Downloads docs for cases with 0 documents
- `scripts/backfill_document_events.py` - Links existing docs to events
- `scripts/cleanup_documents.py` - Removes duplicate document entries

### Database Tables
`cases`, `case_events`, `parties`, `hearings`, `documents`, `scrape_logs`, `scheduler_config`, `users`

## Critical Design Decisions

1. **Deadlines from events ONLY** - PDF OCR unreliable for handwritten dates. Use `event_date + 10 business days`
2. **NC G.S. 45-21.27** - If 10th day falls on weekend/holiday, extends to next business day
3. **PDF extraction** - Only used for bid amounts, NOT deadlines
4. **Headless=False** - Angular pages fail in headless mode
5. **Documents linked to events** - `documents.event_id` foreign key ties PDFs to case_events
6. **Address extraction patterns** - Comma-optional patterns for OCR text (handles variations)

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
