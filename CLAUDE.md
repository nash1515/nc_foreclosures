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

## Current Status (Dec 13, 2025)

- **2,125 cases** across 6 counties (Wake, Durham, Harnett, Lee, Orange, Chatham)
- **Active upset_bid cases:** 37 (all with complete data)
- **Scheduler running** 5 AM Mon-Fri (3-day lookback on Mondays)
- **Frontend:** React + Flask API (Dashboard with county filtering, improved layout)
- **Review Queue:** Fixed skipped cases filter (7-day lookback), Approve/Reject working

### Recent Session Changes (Dec 13)
- **Implemented self-diagnosis system for upset_bid cases:**
  - Three-tier healing approach: re-extract → re-OCR → re-scrape
  - Runs as Task 5 in `daily_scrape.py` after all scraping/monitoring
  - Detects missing critical fields: sale_date, upset_deadline, property_address, current_bid
  - Successfully healed 2 cases with missing sale_date on first run
  - Dry-run mode available for testing (`dry_run=True`)

### Previous Session Changes (Dec 12 - Session 3)
- **Fixed extraction pipeline for monitored cases:**
  - Root cause: `case_monitor.py` wasn't calling full extraction after updates
  - Root cause: Documents only downloaded for upset_bid events, not sale events
  - Added `update_case_with_extracted_data()` call after monitoring
  - Added `has_sale_events` check to trigger document downloads
  - Now downloads Report of Sale PDFs as soon as sale events are detected
- **Fixed bid amount extraction:**
  - Allow bid updates when new amount is higher (required for upset bids)
  - Added "REPORT OF SALE" detection (was only matching "REPORT OF FORECLOSURE SALE")
  - Added multiline "Amount Bid" pattern for OCR with field label on separate line
  - Added back-calculation from "Minimum Amount of Next Upset Bid" when direct bid is missing
    - Handles credit bid scenarios where bank buys back property
    - `current_bid = minimum_next_bid / 1.05`
- **Result:** All 37 upset_bid cases now have complete address + bid data (was 27/37)

### Previous Session Changes (Dec 12 - Session 2)
- **Classifier defense-in-depth:** Added `SALE_CONFIRMED_EVENTS` patterns (Order Confirming Sale, Confirmation of Sale, etc.)
  - Now logs "high confidence" when BOTH time passed AND confirmation event present
  - 118 of 355 closed_sold cases have dual verification
  - Added exclusions for reversed confirmations (set aside, vacated, denied)

### Previous Session Changes (Dec 12 - Session 1)
- **Historical backfill completed:** 2020-01-01 to 2025-11-24 (426 chunks, 71 months × 6 counties)
  - Added 353 new cases (1,770 → 2,123 total)
  - Manually added case 17SP003010-910 (2017 Wake County active upset bid)
  - Dismissed 3,182 skipped cases from backfill to clean up review queue
- **Review Queue bug fix:** Skipped cases filter now uses 7-day lookback on `scrape_date` (was showing 0 due to date field mismatch)

### Previous Session Changes (Dec 11)
- **Unified scraper architecture:** Deleted `initial_scrape.py`, `batch_initial_scrape.py`, `parallel_batch_scrape.py`
- **New scrapers:** `batch_scrape.py` and `parallel_scrape.py` with configurable chunking (daily/weekly/monthly/quarterly/yearly)
- **Skip-existing:** Default behavior skips cases already in DB (use `--refresh-existing` to override)
- **Per-county flag:** `--per-county` searches 1 county at a time to avoid portal result limits
- Added `common/date_utils.py` with `generate_date_chunks()` utility
- Fixed 4 missing cases (25SP002519-910, 24SP000376-910, 25SP000050-910, 25SP002123-910) - filed before initial scrapes

### Classifications
| Status | Count | Description |
|--------|-------|-------------|
| upcoming | 1,451 | Foreclosure initiated, no sale |
| upset_bid | 37 | Sale occurred, within 10-day bid period |
| blocked | 70 | Bankruptcy/stay in effect |
| closed_sold | 355 | Past upset period |
| closed_dismissed | 67 | Case dismissed |

## Key Commands

```bash
# Daily scrape (manual)
./scripts/run_daily.sh

# Scheduler control
./scripts/scheduler_control.sh status|start|stop|logs

# Monitor specific cases
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upset_bid

# Date range scraping (single search)
PYTHONPATH=$(pwd) venv/bin/python scraper/date_range_scrape.py \
  --start 2024-01-01 --end 2024-01-31

# Batch scraping (sequential chunks)
PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
  --start 2024-01-01 --end 2024-12-31 --chunk monthly

# Parallel scraping (concurrent chunks)
PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
  --start 2024-01-01 --end 2024-12-31 --chunk monthly --workers 3

# Download missing documents
PYTHONPATH=$(pwd) venv/bin/python scripts/download_missing_documents.py

# Run self-diagnosis manually
PYTHONPATH=$(pwd) venv/bin/python -c "from scraper.self_diagnosis import diagnose_and_heal_upset_bids; print(diagnose_and_heal_upset_bids(dry_run=False))"

# Database queries
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost
```

## Architecture

### Modules
- `scraper/` - Playwright scraper with CAPTCHA solving (CapSolver)
  - `date_range_scrape.py` - Direct date range scraping
  - `batch_scrape.py` - Sequential batch scraping with chunking
  - `parallel_scrape.py` - Parallel batch scraping for performance
  - `case_monitor.py` - Monitor existing cases (no CAPTCHA)
  - `daily_scrape.py` - Daily automation orchestrator
- `extraction/` - Regex extraction + classification from OCR text
- `scheduler/` - Daily scrape automation (5 AM Mon-Fri)
- `web_app/` - Flask API with Google OAuth
- `frontend/` - React + Vite + Ant Design
- `ocr/` - PDF text extraction (Tesseract)
- `analysis/` - Claude AI analysis (haiku model)

### Key Files
- `scraper/case_monitor.py` - Monitors existing cases via direct URLs (no CAPTCHA)
- `scraper/daily_scrape.py` - Orchestrates daily tasks (3-day lookback on Mondays)
- `scraper/self_diagnosis.py` - Auto-healing for upset_bid cases with missing data
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
