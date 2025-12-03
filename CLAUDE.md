# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NC Foreclosures Project - A data analysis and foreclosure tracking system for North Carolina.

**Repository:** https://github.com/nash1515/nc_foreclosures

**Note:** This is a new project in early setup phase. Project specifications are documented in "NC Foreclosures Project_StartUp Doc.docx".

## Context Window Management Strategy

**CRITICAL:** To maximize context window efficiency, always use GitHub for collaboration and tracking:

### Git Workflow for Context Management
1. **Commit frequently** - Small, focused commits preserve context and enable rollback
2. **Push immediately after commits** - Keep GitHub as the source of truth
3. **Use descriptive commit messages** - Future Claude instances need clear history
4. **Create branches for features** - Isolate work to reduce cognitive load
5. **Use GitHub Issues** - Track bugs, features, and tasks outside of code context
6. **Leverage pull requests** - Document major changes with descriptions and reviews
7. **Tag important milestones** - Mark stable versions for easy reference

### When Working with Claude Code
- Always commit and push before starting major refactoring
- Use `git status` and `git diff` to understand current state efficiently
- Prefer reading recent commits over re-reading entire files
- Use GitHub CLI (`gh`) to manage issues, PRs, and releases
- Reference commit SHAs and file paths with line numbers in discussions

### Essential Git Commands
```bash
# Quick status check
git status

# Stage and commit changes
git add <file>
git commit -m "descriptive message"

# Push to GitHub
git push

# View recent changes
git log --oneline -10
git diff

# Create feature branch
git checkout -b feature/name

# View file history
git log -p <file>
```

### GitHub CLI Commands
```bash
# Create issue
gh issue create --title "title" --body "description"

# List issues
gh issue list

# Create PR
gh pr create --title "title" --body "description"

# View PR status
gh pr status
```

## Project Status

**Phase 1 Foundation:** ✅ Complete (100%)
**Phase 2 PDF & OCR:** ✅ Complete (100%)
**Phase 2.5 Extraction:** ✅ Complete (100%)
**Initial Scrape (2020-2025):** ✅ Complete + Retries Done
**Daily Scrape Scheduler:** ✅ Complete (5 AM Mon-Fri)
**Current Branch:** `main`

### Completed Components
- ✅ PostgreSQL database with full schema (7 tables + new extraction fields)
- ✅ SQLAlchemy ORM models
- ✅ VPN verification system (OpenVPN + FrootVPN)
- ✅ CapSolver reCAPTCHA integration
- ✅ Playwright scraper framework with stealth mode
- ✅ Kendo UI Grid parsing implementation
- ✅ Case detail page parsing (ROA Angular app)
- ✅ Foreclosure case identification
- ✅ Comprehensive data extraction (parties, events, hearings)
- ✅ PDF downloading (Playwright-based)
- ✅ OCR processing module (Tesseract + pdf2image)
- ✅ Batch scrape script (quarterly/monthly strategy)
- ✅ Extraction module (regex-based data parsing from OCR text)
- ✅ Classification module (upcoming/upset_bid status)
- ✅ **NEW: Parallel batch scraper** (6 browsers simultaneously)
- ✅ **NEW: Failure tracking system** (JSON-based retry capability)
- ✅ **NEW: Scheduler service** (5 AM Mon-Fri, configurable via API)
- ✅ **NEW: PDF bid extraction for upset_bid cases** (AOC-SP-403 form parsing)

### Scrape Progress (as of Nov 27, 2025 - ALL COUNTIES COMPLETE)

| Year | Wake (910) | Durham (310) | Harnett (420) | Lee (520) | Orange (670) | Chatham (180) | Total |
|------|------------|--------------|---------------|-----------|--------------|---------------|-------|
| 2020 | 102 | 10 | 8 | 4 | 6 | 0 | 130 |
| 2021 | 61 | 8 | 7 | 6 | 1 | 0 | 83 |
| 2022 | 92 | 27 | 12 | 19 | 4 | 1 | 155 |
| 2023 | 113 | 34 | 29 | 22 | 16 | 1 | 215 |
| 2024 | 173 | 76 | 20 | 13 | 17 | 11 | 310 |
| 2025 | 489 | 142 | 105 | 34 | 30 | 23 | 823 |
| **Total** | **1,030** | **297** | **181** | **98** | **74** | **36** | **1,716** |

**Notes:**
- All 6 counties fully scraped (2020-2025)
- Chatham County issue resolved - was temporary portal bug
- See `data/scrape_failures/ALL_MISSING_TIMEFRAMES.md` for full details

### Next Steps
1. ~~Run full initial scrape for all 6 counties (2020-2025)~~ ✅ Complete
2. ~~Retry failed date ranges~~ ✅ Complete
3. ~~Investigate Chatham County portal issues~~ ✅ Resolved (was temporary portal bug)
4. ~~Set up Claude API for AI analysis~~ ✅ Complete
5. ~~Run classifier on unclassified cases~~ ✅ Complete (new states: blocked, closed_sold, closed_dismissed)
6. ~~Implement daily scrape functionality (include monitoring of `blocked` cases)~~ ✅ Complete
7. ~~Re-scrape NULL event types~~ ✅ Complete (5,461 events added, 112 classifications updated)
8. ~~Set up automated daily scraping~~ ✅ Complete (scheduler service + API)
9. Build frontend web application (scheduler config UI included)
10. Implement enrichment module (Zillow, county records, tax values)
11. Analyze `closed_sold` cases (183) for bidding strategy patterns by county

### Recent Updates (Dec 3, 2025) - Session 16 (PDF Bid Extraction)
- **PDF Document Download for Upset Bid Cases:**
  - New `download_all_case_documents()` function downloads ALL documents for upset_bid cases
  - Documents stored in `data/pdfs/{county}/{case_number}/`
  - Skips existing documents to avoid re-downloading
  - Enables complete AI analysis context (mortgage info, deed details, attorney info)
- **AOC-SP-403 (Notice of Upset Bid) Extraction:**
  - New patterns in `extraction/extractor.py` for NC standard upset bid form
  - Handles OCR artifacts (extra spaces, typos like "UpsetBd", "M nimum")
  - Position-based extraction for columnar form layouts
  - Extracts: current_bid, previous_bid, minimum_next_bid, deadline, deposit
  - Smart fallback: calculates current_bid from minimum_next_bid/1.05 when handwritten amounts are garbled
- **Case Monitor Integration:**
  - Only downloads/extracts for `upset_bid` cases (not `upcoming`)
  - OCR processes upset bid and sale documents for bid data
  - Verifies PDF data against HTML-extracted bids when available
- **Test Results:**
  - Case 24SP001280-670: $47,256 bid, $49,612.50 min next, deadline 12/4/2025
  - Case 25SP000122-670: $55,983.62 bid (calculated), deadline 12/11/2025
  - 22 of 24 upset_bid cases now have complete bid data

### Previous Updates (Dec 3, 2025) - Session 15 (Scheduler Service)
- **Automated Daily Scrape Scheduler:**
  - **New `scheduler/` module** with database-driven configuration
  - **Default schedule**: 5:00 AM Mon-Fri, scrapes previous day's cases
  - **Frontend-configurable** via REST API endpoints
  - **Components created:**
    - `scheduler/scheduler_service.py` - Daemon that runs scheduled jobs
    - `scheduler/api.py` - Flask API for frontend configuration
    - `scheduler/nc-foreclosures-scheduler.service` - systemd service file
    - `scripts/scheduler_control.sh` - Helper for install/start/stop/logs
  - **Database**: New `scheduler_config` table stores schedule settings
  - **API Endpoints:**
    - `GET /api/scheduler/config` - View all job configs
    - `PUT /api/scheduler/config/daily_scrape` - Update schedule (hour, minute, days)
    - `POST /api/scheduler/config/daily_scrape/toggle` - Enable/disable
    - `POST /api/scheduler/run/daily_scrape` - Trigger manual run
    - `GET /api/scheduler/history` - View scrape history
- **Bug Fixes:**
  - Fixed `date_range_scrape.py` field mapping bugs (scrape_log_id, party_name, event_date, hearing fields)
  - 7 new foreclosures added from Dec 2-3 daily scrape
- **Database Total:** 1,724 cases (was 1,717)

### Previous Updates (Dec 3, 2025) - Session 14 (Partition Sales Support)
- **Expanded Case Detection to Include Partition Sales:**
  - **Problem**: Partition sales (co-owner forced sales) have upset bid opportunities but weren't being captured
  - **Example**: Case 24SP000044-910 - Partition sale with $304,500 upset bid, Case Type = "Special Proceeding" (not Foreclosure)
  - **Solution**: Added `UPSET_BID_OPPORTUNITY_INDICATORS` to `is_foreclosure_case()` in `scraper/page_parser.py`
  - **New Indicators**: `report of sale`, `order allowing partition by`, `partition by sale`
  - **Effect**: Daily scrape will now capture partition sales and other non-foreclosure upset bid opportunities
  - **Note**: Not retroactive - only applies to new daily scrapes going forward

### Previous Updates (Dec 2, 2025) - Session 13 (Bot Detection Fix)
- **Bot Detection Issue Fixed:**
  - **Problem**: Daily scrape new case search failing with CAPTCHA timeout (portal returned 403 Forbidden)
  - **Root Cause**: NC Courts Portal started blocking requests without proper User-Agent header
  - **Solution**: Added Chrome user-agent to all Playwright browser contexts
  - **Files Updated:**
    - `scraper/date_range_scrape.py` - Added user-agent to browser context
    - `scraper/initial_scrape.py` - Added user-agent to browser context
    - `scraper/case_monitor.py` - Added user-agent to browser context
    - `scraper/capture_portal_structure.py` - Added user-agent to browser context
    - `scraper/explore_portal.py` - Added user-agent to browser context
- **County Detection Bug Fixed:**
  - **Problem**: Search results page column order changed, location field showing date instead of county
  - **Solution**: Now extracts county from case number suffix (e.g., `25SP001116-310` → 310 = Durham)
  - Case number format: `YYSPNNNNNN-CCC` where `CCC` is the county code

### Previous Updates (Dec 2, 2025) - Session 12 (Database Completion & Retry Logic)
- **Retry Logic Added to Case Monitor:**
  - `scraper/case_monitor.py` now has exponential backoff retry (default: 3 retries)
  - Clears Angular SPA state between page loads (`about:blank` navigation)
  - Validates page content before accepting (checks for `roa-label` class)
  - CLI options: `--max-retries`, `--retry-delay`, `--headless`
  - Default: visible browser (`headless=False`) for reliability
- **New Re-scrape Script:**
  - `scraper/rescrape_null_events.py` - Re-scrapes cases with NULL event types
  - Uses case_monitor with retry logic for 100% success rate
- **Portal URL Format Migration:**
  - Tyler Technologies changed URL format: `?id=...` → `#/.../anon/portalembed`
  - All 1,716 case URLs migrated to new format
- **Database Completion Results:**
  - Re-scraped 845 cases with NULL event types
  - Added 5,461 new events with proper types
  - 112 classifications updated based on new event data
  - **0 errors** after retry logic applied
- **Classification Changes Detected:**
  - 75 `upcoming` → `closed_sold` (sales completed)
  - 17 `blocked` → `closed_sold` (bankruptcy resolved)
  - 13 `upcoming` → `upset_bid` (new opportunities!)
  - 5 `upcoming` → `closed_dismissed`
  - 2 other changes
- **Current Database Status (Dec 2, 2025):**
  - **1,372** upcoming
  - **183** closed_sold (up from 91)
  - **77** blocked (down from 107)
  - **53** closed_dismissed
  - **22** upset_bid (up from 7 - 3x more opportunities!)
  - **9** unclassified

### Previous Updates (Dec 1, 2025) - Session 11 (Daily Scraping System)
- **Daily Scraping System Implemented:**
  - `scraper/daily_scrape.py` - Main orchestrator with 3 tasks:
    1. **New Case Search**: Search portal for cases filed yesterday (uses CAPTCHA)
    2. **Case Monitoring**: Check existing cases via direct URLs (NO CAPTCHA)
    3. **Stale Reclassification**: Update time-based classifications
  - `scraper/case_monitor.py` - Monitors `upcoming`, `blocked`, and `upset_bid` cases
    - Detects new events (sale reports, upset bids, bankruptcies)
    - Updates `current_bid_amount` and `minimum_next_bid` for new upset bids
    - Triggers reclassification based on detected events
  - `scripts/run_daily.sh` - Wrapper script for cron/manual execution
- **Database Updates:**
  - Added `minimum_next_bid` column (NC law: current_bid * 1.05)
  - Extraction module now auto-calculates minimum_next_bid
- **VPN Requirement Removed:**
  - VPN verification removed from all scrapers
  - Can be re-enabled if IP banning becomes an issue
- **Classification Monitoring:**
  - `upcoming` → Check for sale events → `upset_bid`
  - `blocked` → Check for bankruptcy dismissal → `upcoming`
  - `upset_bid` → Check for new bids (extend deadline) or blocking events → `blocked`
  - `upset_bid` → Deadline passes with no new bids → `closed_sold`
- **Critical Fixes During Testing:**
  - Angular pages don't load in headless mode - set `headless=False` as default
  - Added classification preservation logic - prevents losing existing classifications when classifier returns None
  - Many database events have empty `event_type` fields from initial scrape
- **First Daily Run Results (Dec 1, 2025):**
  - New case search: 0 cases (Nov 30 was Saturday)
  - Case monitoring (50 case sample): Working correctly, 0 new events detected
  - Full monitoring run estimate: ~1.5 hours for 1,567 cases

### TODO for Next Session
1. **Set up cron job** for automated daily scraping
2. **Enrichment module** - Add property data from Zillow, county tax records
3. **Bidding strategy analysis** - Analyze 183 closed_sold cases for patterns

### Previous Updates (Dec 1, 2025) - Session 10 (VPN Fix)
- **WSL2 VPN Routing Issue FIXED:**
  - **Problem**: VPN connection caused Claude Code to hang for 30+ minutes
  - **Root Cause**: OpenVPN's `redirect-gateway` broke WSL2's virtual network bridge to Windows
  - **Solution**: Modified all 6 US FrootVPN config files with routing directives
  - **Result**: VPN and Claude API now work simultaneously
  - See "WSL2 VPN Routing Fix" section for full details

### Previous Updates (Dec 1, 2025) - Session 9 Continued (Classification Cleanup)
- **New Classification States Added:**
  - `upcoming`: Foreclosure initiated, no sale yet (1,460 cases)
  - `upset_bid`: Sale occurred, within 10-day upset period (0 currently)
  - `blocked`: Bankruptcy/stay in effect - monitor for changes (107 cases)
  - `closed_sold`: Sale completed, past upset period (91 cases) - valuable for bidding strategy analysis
  - `closed_dismissed`: Case dismissed/terminated (49 cases)
- **Classifier Improvements** (`extraction/classifier.py`):
  - Added recognition for legacy event terminology (Petition, Cause of Action) for 2020-2022 cases
  - Separate handling for bankruptcy (blocked) vs dismissal (closed_dismissed)
  - Cases with Report of Sale past upset period now properly classified as `closed_sold`
- **Data Cleanup Results:**
  - Before: 248 NULL, 201 needs_review, confusing state
  - After: Only 9 truly unclassified cases, clear categories
- **Daily Scrape Reminder:** `blocked` cases (107) need monitoring for bankruptcy dismissal/stay lifted

### Previous Updates (Nov 30, 2025) - Session 9 (AI Analysis Setup)
- **Claude API Integration Complete:**
  - Added `ANTHROPIC_API_KEY` to `.env` and `common/config.py`
  - Fixed model IDs in `analysis/api_client.py` (haiku: `claude-3-5-haiku-20241022`)
  - Tested successfully with haiku model (~$0.003 per small case, ~$0.02 for 18 docs)
  - **Default model set to haiku** (cost-effective, good accuracy)
- **AI Analysis Guardrails Added:**
  - `run_analysis.py`: Refuses to analyze non-`upset_bid` cases with clear error message
  - `case_analyzer.py`: Safety net prevents AI from overwriting `upcoming` or `closed` classifications
  - AI can only refine `upset_bid` cases (confirm, change to pending, or flag for review)
- **Classification Rules Added to AI Prompts** (`knowledge_base.py`):
  - Clear rules: no Report of Sale = `upcoming`, within 10 days = `upset_bid`, etc.
  - "Missing documents" does NOT mean "needs_review"
- **Output Display Improved** (`run_analysis.py`):
  - Now shows mortgage_info, tax_info, and estimated_total_liens
- **Test Results:**
  - Case 1098 (Lee County, upset_bid): 95% confidence, $121,209.85 bid, Nationstar Mortgage
  - Case 1817 (Wake County, upcoming): Correctly rejected - "AI analysis only runs on upset_bid cases"

### Previous Updates (Nov 27, 2025) - Session 8 (Chatham County Resolution)
- **Chatham County Issue RESOLVED:** Was temporary portal bug, now fixed
  - User reported: checking Chatham checkbox showed different county results
  - Investigation: Used Playwright MCP to manually test portal
  - Finding: Portal now returns correct Chatham County results
- **Chatham County Scrape Completed:**
  - 2020: 0 foreclosures (COVID moratorium)
  - 2021: 0 foreclosures
  - 2022: 1 foreclosure
  - 2023: 1 foreclosure
  - 2024: 11 foreclosures (re-scraped with full year)
  - 2025: 23 foreclosures (previously scraped)
  - **Total Chatham: 36 foreclosures**
- **Final Database Total:** 1,716 foreclosures (+49 from Chatham session)
- **All 6 counties fully scraped for 2020-2025**

### Recent Updates (Nov 27, 2025) - Session 7 (Retry Session)
- **Retry Session Completed:** All 7 failed date ranges retried successfully
  - Orange Q4 2020: NO CASES (COVID moratorium period)
  - Lee Q3 2020: NO CASES (COVID moratorium period)
  - Orange Q3 2021: NO CASES
  - Wake May 2021: 0 foreclosures (19 other SP cases)
  - Orange Q3 2024: +7 foreclosures added
  - Wake Nov 2025: +55 foreclosures added
  - Wake Dec 2025: NO CASES (future month)
- **Code Improvements Made:**
  1. **"No cases match your search" detection** (`scraper/portal_interactions.py`)
     - Added polling loop to detect empty results message
     - Returns `"no_results"` instead of timing out
  2. **Upsert logic for duplicate cases** (`scraper/initial_scrape.py`)
     - Check for existing cases before INSERT
     - Update existing cases instead of failing on duplicates
     - Only add parties/events/hearings for NEW cases
- **Final Database Total:** 1,667 foreclosures (+62 from retry session)

### Previous Updates (Nov 25, 2025) - Session 6
- **Parallel Batch Scraper:** New `scraper/parallel_batch_scrape.py`
  - Runs all 6 counties simultaneously with ThreadPoolExecutor
  - Each county gets its own browser instance
  - Configurable worker count (default: 6)
  - Automatic failure tracking to JSON files
  - `--retry-failures` flag to retry only failed date ranges
- **Failure Tracking System:**
  - Failed ranges saved to `data/scrape_failures/failures_YYYY.json`
  - Human-readable summary in `data/scrape_failures/ALL_MISSING_TIMEFRAMES.md`
  - Retry commands documented for easy re-running
- **Chatham County Issue:** All searches fail - portal has issues with this county
  - Temporarily excluded from scraping
  - Will investigate and retry later

### Recent Updates (Nov 25, 2025) - Session 5
- **Extraction Module:** New `extraction/` module for structured data extraction
  - `extraction/extractor.py` - Regex-based extraction from OCR text
  - `extraction/classifier.py` - Case status classification (upcoming/upset_bid)
  - `extraction/run_extraction.py` - CLI for batch processing
  - Auto-triggers after OCR processing completes
  - **Extracted fields:** property_address, current_bid_amount, next_bid_deadline, sale_date, legal_description, trustee_name, attorney_name, attorney_phone, attorney_email, classification
- **Database Schema Updates:** Added new columns to cases table:
  - `sale_date`, `legal_description`, `trustee_name`
  - `attorney_name`, `attorney_phone`, `attorney_email`
- **Pipeline:** Scrape -> PDF Download -> OCR -> Extraction (fully automated)

### Recent Updates (Nov 25, 2025) - Session 4
- **PDF Downloading:** New `scraper/pdf_downloader.py` module
  - Downloads documents from case detail pages via Playwright
  - Stores in `data/pdfs/{county}/{case_number}/`
  - Creates Document records in database
- **OCR Processing:** New `ocr/` module (separate from scraper)
  - `ocr/processor.py` - Text extraction using pdftotext and Tesseract
  - `ocr/run_ocr.py` - Standalone CLI for batch OCR processing
  - Run with: `PYTHONPATH=$(pwd) venv/bin/python ocr/run_ocr.py`
- **Batch Scraping:** New `scraper/batch_initial_scrape.py`
  - Wake County: Monthly searches
  - Other 5 counties: Quarterly searches with bi-monthly fallback
  - Dry run mode: `--dry-run`

### Recent Updates (Nov 25, 2025) - Session 3
- **FIXED: Case Type Extraction** - The issue was `&nbsp;` (non-breaking space U+00A0) in HTML labels
- **FIXED: Angular Loading** - Added explicit wait for `table.roa-caseinfo-info-rows` selector
- **ADDED: Comprehensive Data Extraction** - Now captures ALL data from case detail pages:
  - **Style**: Full case title (e.g., "FORECLOSURE (HOA) - Mark Dwayne Ellis")
  - **Parties**: Respondent, Petitioner, Trustee with names (new `parties` table)
  - **Events**: Date, type, filed_by, filed_against, hearing_date, document_url
  - **Hearings**: Date, time, type (new `hearings` table)
- **Database Schema Updates:**
  - Added `parties` table (party_type, party_name)
  - Added `hearings` table (hearing_date, hearing_time, hearing_type)
  - Added `style` column to `cases`
  - Added event detail columns to `case_events`

### Previous Updates (Nov 25, 2025) - Session 2
- **Playwright MCP Debugging:** Used Playwright MCP to examine actual page structures
- **Case Detail Page:** Portal uses "Register of Actions" (ROA) Angular app
  - URL format: `/app/RegisterOfActions/?id={HASH}&isAuthenticated=False&mode=portalembed`
  - Case Type is in `table.roa-caseinfo-info-rows` with "Case Type:" label
- **Foreclosure Identification:**
  1. Case Type = "Foreclosure (Special Proceeding)"
  2. OR events contain: "Foreclosure Case Initiated", "Findings And Order Of Foreclosure", etc.

### Previous Updates (Nov 24, 2025)
- **VPN Setup:** OpenVPN configured with FrootVPN (Virginia server)
- **Portal Discovery:** Portal uses Kendo UI Grid, not simple HTML tables
- **Kendo Grid Support:** Updated selectors for grid, pagination, and pager info
- See `docs/KENDO_GRID_FIXES.md` for detailed implementation notes

## Setup and Development

### Environment Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Set PYTHONPATH (required for imports)
export PYTHONPATH=$(pwd)

# Start PostgreSQL
sudo service postgresql start
```

### Database Commands

```bash
# Initialize database
PYTHONPATH=$(pwd) venv/bin/python database/init_db.py

# Connect to database
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost

# View tables
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\dt"
```

### Running Tests

```bash
# Integration tests
PYTHONPATH=$(pwd) venv/bin/python tests/test_phase1_integration.py

# Test VPN manager
PYTHONPATH=$(pwd) venv/bin/python -c "from scraper.vpn_manager import is_vpn_connected; print(is_vpn_connected())"

# Test CapSolver
PYTHONPATH=$(pwd) venv/bin/python scraper/captcha_solver.py
```

### VPN Setup

**REQUIRED:** VPN must be running before scraping.

**CLAUDE CODE NOTE:** Do NOT run `sudo openvpn` directly - it can hang waiting for password input. Use the helper scripts instead:

```bash
# Check VPN status (safe, no sudo)
./scripts/vpn_status.sh

# Start VPN (handles password and waits for connection)
# NOTE: Requires sudo password - user may need to run manually if it hangs
./scripts/vpn_start.sh [virginia|california|florida|georgia|illinois|newyork|random-east]
```

**Manual VPN start (if scripts don't work):**
```bash
cd ~/frootvpn
sudo openvpn --config "United States - Virginia.ovpn" --auth-user-pass auth.txt --daemon --log /tmp/openvpn.log

# Available US servers:
# - United States - Virginia.ovpn
# - United States - California.ovpn
# - United States - Florida.ovpn
# - United States - Georgia.ovpn
# - United States - Illinois.ovpn
# - United States - New York.ovpn

# Verify VPN is connected
curl ifconfig.me  # Should NOT show baseline IP (136.61.20.173)

# Stop VPN
sudo killall openvpn
```

### WSL2 VPN Routing Fix (Dec 1, 2025)

**Problem:** When OpenVPN runs inside WSL2, connecting to VPN would cause Claude Code to hang for 30+ minutes. The Windows host worked fine - only WSL2 was affected.

**Root Cause:** OpenVPN's `redirect-gateway` directive replaces the default route, breaking WSL2's virtual network bridge to Windows. All traffic tries to go through the VPN tunnel but the return path is broken, and DNS also fails because WSL2 uses Windows for DNS resolution.

**Fix Applied:** Added routing directives to all 6 US FrootVPN config files (`~/frootvpn/United States - *.ovpn`):

```
# WSL2 routing fix - preserve local network connectivity
# Route Anthropic API through original gateway (prevents Claude Code hanging)
route 160.79.104.0 255.255.255.0 net_gateway
# Route GitHub through original gateway (for git push)
route 140.82.112.0 255.255.255.0 net_gateway
# Keep WSL2 internal network using original gateway
route 172.16.0.0 255.240.0.0 net_gateway
```

**What these directives do:**
- `route 160.79.104.0 255.255.255.0 net_gateway` - Route Anthropic API (160.79.104.x) through original Windows NAT gateway
- `route 140.82.112.0 255.255.255.0 net_gateway` - Route GitHub (140.82.112.x) through original gateway
- `route 172.16.0.0 255.240.0.0 net_gateway` - Keep WSL2 internal network using original gateway

**How it works:** FrootVPN uses redirect-gateway which routes ALL traffic through VPN. Our fix adds explicit routes for Anthropic API, GitHub, and WSL2 internal networks BEFORE the redirect takes effect. These more-specific routes take priority over the VPN default route.

**Result:**
- NC Courts scraping traffic → VPN tunnel (shows VPN IP 74.115.214.x)
- Claude Code API traffic → Original Windows NAT (no timeout!)
- GitHub push/pull → Original Windows NAT (no timeout!)
- WSL2 internal traffic → Original Windows NAT

**Rollback:** If the fix causes issues, remove the 5 lines above from the `.ovpn` files.

### Running the Scraper

**Prerequisites:**
1. PostgreSQL running: `sudo service postgresql start`
2. CapSolver API key in `.env`
3. VPN is **optional** (removed as of Dec 1, 2025) - re-enable if IP banning occurs

```bash
# Test with small limit
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --test \
  --limit 1

# Full scrape (after testing)
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-12-31
```

### Running the Daily Scraper

The daily scraper has two main functions:
1. **New Case Search**: Search portal for cases filed yesterday (requires CAPTCHA)
2. **Case Monitoring**: Check existing cases via direct URLs (NO CAPTCHA needed)

```bash
# Run all daily tasks (search new + monitor existing)
./scripts/run_daily.sh

# Search for new cases only (skip monitoring)
./scripts/run_daily.sh --search-only

# Monitor existing cases only (skip new case search)
./scripts/run_daily.sh --monitor-only

# Dry run - see what would be done
./scripts/run_daily.sh --dry-run

# Search for specific date (default: yesterday)
PYTHONPATH=$(pwd) venv/bin/python scraper/daily_scrape.py --date 2025-11-30
```

**Cron Setup (run at 6 AM daily):**
```bash
0 6 * * * /home/ahn/projects/nc_foreclosures/scripts/run_daily.sh >> /home/ahn/projects/nc_foreclosures/logs/cron.log 2>&1
```

**Monitoring Only (no CAPTCHA needed):**
```bash
# Monitor specific classification
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upcoming
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification blocked
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upset_bid

# Limit number of cases to check
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --limit 10

# Dry run
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --dry-run
```

### Scheduler Service (Automated Daily Scraping)

The scheduler runs as a background service and executes the daily scrape at the configured time.

**Setup:**
```bash
# Install as systemd service (one-time)
./scripts/scheduler_control.sh install

# Start the scheduler
./scripts/scheduler_control.sh start

# Check status and logs
./scripts/scheduler_control.sh status
./scripts/scheduler_control.sh logs  # Follow logs in real-time

# Stop the scheduler
./scripts/scheduler_control.sh stop
```

**Default Schedule:** 5:00 AM Mon-Fri, scrapes previous day's cases.

**API Configuration (for frontend):**
```bash
# View current schedule
curl http://localhost:5000/api/scheduler/config/daily_scrape

# Update schedule to 6:30 AM
curl -X PUT http://localhost:5000/api/scheduler/config/daily_scrape \
  -H "Content-Type: application/json" \
  -d '{"schedule_hour": 6, "schedule_minute": 30}'

# Change days (weekends only)
curl -X PUT http://localhost:5000/api/scheduler/config/daily_scrape \
  -H "Content-Type: application/json" \
  -d '{"days_of_week": "sat,sun"}'

# Enable/disable scheduler
curl -X POST http://localhost:5000/api/scheduler/config/daily_scrape/toggle

# Trigger manual run (scrapes yesterday by default)
curl -X POST http://localhost:5000/api/scheduler/run/daily_scrape

# Trigger run for specific date
curl -X POST http://localhost:5000/api/scheduler/run/daily_scrape \
  -H "Content-Type: application/json" \
  -d '{"target_date": "2025-12-02"}'

# View scrape history
curl http://localhost:5000/api/scheduler/history?limit=10
```

## Architecture Overview

### Database Schema
- `cases` - Main foreclosure case information
- `case_events` - Timeline of case events
- `documents` - PDF files and OCR text
- `scrape_logs` - Audit trail of scraping activity
- `user_notes` - User annotations (for web app)
- `scheduler_config` - Scheduled job configuration (editable via API)

### Module Structure
- `common/` - Shared utilities (config, logging, county codes)
- `database/` - ORM models and connection management
- `scraper/` - Web scraping (VPN, CAPTCHA, Playwright)
- `scheduler/` - Automated job scheduling (database-driven, API-configurable)
- `ocr/` - PDF processing (Phase 2)
- `analysis/` - AI analysis (Phase 3)
- `web_app/` - Flask app (Phase 4)
- `tests/` - Integration tests

### Key Files
- `database/schema.sql` - PostgreSQL schema
- `database/models.py` - SQLAlchemy ORM models
- `scraper/initial_scrape.py` - Main scraper script
- `scraper/daily_scrape.py` - Daily scrape orchestrator
- `scraper/case_monitor.py` - Case monitoring module (direct URL access)
- `scraper/vpn_manager.py` - VPN verification (currently disabled)
- `scraper/captcha_solver.py` - reCAPTCHA solving (CapSolver API)
- `scraper/page_parser.py` - Kendo UI Grid HTML parsing
- `scraper/portal_interactions.py` - Form filling and navigation
- `scraper/portal_selectors.py` - CSS selectors for portal elements
- `scripts/run_daily.sh` - Daily scrape wrapper for cron/manual execution
- `scripts/scheduler_control.sh` - Scheduler service control (install/start/stop/logs)
- `scheduler/scheduler_service.py` - Scheduler daemon
- `scheduler/api.py` - REST API for scheduler configuration

## Configuration

### Environment Variables (.env)
- `DATABASE_URL` - PostgreSQL connection string
- `CAPSOLVER_API_KEY` - CapSolver API key
- `VPN_BASELINE_IP` - Your IP without VPN (for verification)
- `PDF_STORAGE_PATH` - Where to store downloaded PDFs
- `LOG_LEVEL` - Logging verbosity (INFO, DEBUG, etc.)

### County Codes
Target counties: Chatham (180), Durham (310), Harnett (420), Lee (520), Orange (670), Wake (910)

## Important Notes

- **Always use PYTHONPATH:** Required for module imports
- **VPN must be on:** Scraper will exit if VPN not detected (baseline IP: 136.61.20.173, VPN IP: 74.115.214.142)
- **PostgreSQL must be running:** `sudo service postgresql start`
- **Portal uses Kendo UI:** Grid, dropdowns, and pagination all use Kendo components
- **Headless mode issues:** Use `headless=False` for development due to aggressive CAPTCHA detection

## Known Issues

1. ~~**Chatham County Portal Issues:**~~ **RESOLVED** - Was temporary portal bug, now fixed. All 6 counties fully scraped.
2. **CAPTCHA failures with parallel scraping:** Running 6 browsers simultaneously increases CAPTCHA failure rate. Consider reducing to 3-4 workers.
3. **Portal timeouts during peak hours:** Best to scrape during off-peak times (early morning or late night)
4. **Kendo dropdown timeouts:** Status and case type dropdowns timing out after 10s (county works via JS fallback)
5. **CAPTCHA solving delays:** CapSolver API can be slow, adjust timeouts if needed
6. **Browser detection:** Automated browsers trigger image CAPTCHAs instead of checkbox
7. ~~**WSL2 VPN Routing Issue:**~~ **FIXED (Dec 1, 2025)** - VPN connection broke WSL2 network, causing 30+ minute hangs. Fixed by modifying OpenVPN configs. See "WSL2 VPN Routing Fix" section above.

## Documentation

- `docs/KENDO_GRID_FIXES.md` - Kendo UI implementation details (Nov 24, 2025)
- `docs/SESSION_SUMMARY.md` - Previous session summary
- `docs/SETUP.md` - Detailed setup instructions
- `docs/plans/2025-11-24-nc-foreclosures-architecture-design.md` - Full architecture
- `docs/plans/2025-11-24-phase1-foundation-implementation.md` - Phase 1 plan
- `PROJECT_REQUIREMENTS.md` - Original requirements
