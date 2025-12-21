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

## Current Status (Dec 21, 2025)

- **2,156 cases** across 6 counties (Wake, Durham, Harnett, Lee, Orange, Chatham)
- **Active upset_bid cases:** 42 (18 Wake, 24 other counties)
- **Scheduler running** 5 AM Mon-Fri (3-day lookback on Mondays) + **catch-up logic on startup**
- **Frontend:** React + Flask API (Dashboard, Admin tab for admins, Case Detail with bid ladder)
- **Review Queue:** Fixed skipped cases filter (7-day lookback), Approve/Reject working
- **Claude Vision OCR:** Fallback for handwritten bid amounts on Report of Sale/Upset Bid documents
- **AI Analysis Module:** MERGED to main - comprehensive 4-section analysis
- **Wake RE Enrichment:** 18/18 Wake cases enriched ✓, router in place for other counties

### Recent Session Changes (Dec 21 - Session 19)
- **County Router for Enrichments:**
  - Added `enrichments/router.py` to dispatch to county-specific enrichers
  - Routes based on case_number suffix (e.g., `-910` → Wake, `-310` → Durham)
  - Returns `skipped: True` for counties without implemented enrichers
  - Updated `classifier.py` to trigger enrichment for ALL upset_bid cases (router handles filtering)
- **Wake RE Enrichment - 18/18 cases now enriched:**
  - Fixed address extraction bug: Two-column OCR bleed captured "Credit Union" from adjacent column
    - Pattern 8 now stops at street type designator instead of newline
  - Fixed same account_id matching: Condos with multiple rows (834 and 834-3D) now recognized as single match
  - Fixed malformed addresses: Parser now detects city names merged with street (missing comma separator)
  - Added two-step AddressSearch for directional prefixes (N/S/E/W/NE/NW/SE/SW):
    - Step 1: GET AddressSearch.asp to get list of street variations
    - Step 2: POST with selected locid to get property results
- **Data cleanup:**
  - Deleted 16 orphaned test records from enrichments table
  - Added NOT NULL constraint on `enrichments.case_id` to prevent future orphans
- **Files changed:**
  - `enrichments/router.py` (NEW) - County-based enrichment router
  - `enrichments/__init__.py` - Export enrich_case from router
  - `enrichments/common/address_parser.py` - Handle malformed addresses with missing city comma
  - `enrichments/wake_re/config.py` - Add AddressSearch URL templates
  - `enrichments/wake_re/url_builder.py` - Add build_address_search_url()
  - `enrichments/wake_re/scraper.py` - Add two-step search, same account_id matching
  - `enrichments/wake_re/enricher.py` - Route to two-step search when prefix present
  - `extraction/extractor.py` - Fix Pattern 8 to stop at street type
  - `extraction/classifier.py` - Generic enrichment trigger for all upset_bid cases

### Previous Session Changes (Dec 19 - Session 18)
- **AI Analysis Module merged to main:**
  - Enhanced prompt with comprehensive 4-section analysis structure:
    - I. Executive Summary (4-6 sentence overview)
    - II. Analysis of Parties (plaintiff/defendant in 2-column layout)
    - III. Legal & Procedural Analysis (statute citations, compliance review)
    - IV. Conclusion & Key Takeaways (investment considerations)
  - Removed chronological timeline (too verbose per user feedback)
  - Removed Other Parties section
  - Added NC foreclosure statute references (G.S. 45-21.16 through 45-21.33)
  - Improved default_amount vs total_debt extraction guidance
  - Increased max_tokens to 8192 for longer responses
  - Added `comprehensive_analysis` JSONB column to case_analyses table
  - Cost: ~$0.31 per case (increased from ~$0.02 due to larger response)
- **Parcel ID discovery:** Found parcel IDs in 1,033+ documents
  - Wake County: 10-digit format (e.g., `0787005323`)
  - Durham: 10-digit format (e.g., `0831912409`)
  - Formats vary by county - potential for QuickLinks integration
- **Files changed:**
  - `analysis/prompt_builder.py` - Comprehensive 4-section prompt structure
  - `analysis/analyzer.py` - Parse comprehensive_analysis, increased max_tokens
  - `database/models.py` - Added comprehensive_analysis column
  - `web_app/api/analysis.py` - Return comprehensive_analysis in API
  - `frontend/src/components/AIAnalysisSection.jsx` - 4-section UI with 2-column parties
  - `migrations/add_comprehensive_analysis.sql` (NEW) - Schema migration

### Previous Session Changes (Dec 19 - Session 17)
- **Case Detail page layout update:**
  - Bid Information and Team Notes now side-by-side in same row
  - Team Notes card height matches Bid Information card
  - AI Analysis section moved directly under those two tiles
  - Parties/Contacts/Events pushed below AI Analysis
- **Files changed:**
  - `frontend/src/pages/CaseDetail.jsx` - Layout reorganization
  - `frontend/src/components/NotesCard.jsx` - Added style prop for height matching

### Previous Session Changes (Dec 19 - Session 16)
- **Root cause analysis: Case 25SP001804-910 missing from dashboard**
  - Case was in `skipped_cases` table, dismissed on Dec 12
  - New "Report of Sale" event added Dec 18 - but dismissed cases are never re-checked
  - **Root cause:** Parser bug - event types split across HTML elements weren't captured
    - Portal rendered: `<div>Order</div><div>for Sale of Ward's Real Property</div>`
    - Parser saw "Order" (too short) + "for Sale..." (lowercase) → `event_type = NULL`
  - **Impact:** 3,118 events with NULL event_type across 964 cases
- **Parser fix (`page_parser.py:385-433`):**
  - Added fallback logic to concatenate adjacent short lines that form split event types
  - Now correctly captures "Order for Sale of Ward's Real Property"
- **New indicator:** Added `'order for sale'` to `SALE_DOCUMENT_INDICATORS` for earlier detection
- **Backfill completed (`scripts/backfill_event_types.py`):**
  - Re-parsed 959 cases with NULL event types
  - Fixed 2,411 events (78% of affected)
  - 692 remaining NULL events (genuinely missing or edge cases)
- **Reclassification:** 9 expired cases moved from `upcoming`/`upset_bid` → `closed_sold`
- **Cases recovered/promoted:**
  - `25SP001804-910` - Recovered from skipped_cases → `upset_bid` (deadline 12/29)
  - `25SP002745-910` - Promoted from skipped_cases → `upcoming` (partition case)
- **New script: `scripts/reevaluate_dismissed_cases.py`**
  - Re-fetches fresh events for all 3,314 dismissed skipped cases
  - Checks if any now match sale indicators
  - Promotes matching cases to main `cases` table
  - Generates detailed markdown report at `logs/reevaluate_report.md`
  - **Scheduled to run at 5 PM today** (~6 hours, 4 workers)
- **Files changed:**
  - `scraper/page_parser.py` - Multi-line event type parsing fix + new indicator
  - `scripts/backfill_event_types.py` (NEW) - Backfill NULL event types
  - `scripts/reevaluate_dismissed_cases.py` (NEW) - Re-evaluate dismissed skipped cases
  - `scripts/run_reevaluate_once.sh` (NEW) - One-time cron script

### Previous Session Changes (Dec 19 - Session 15)
- **AI Analysis Module (feature/ai-analysis branch):**
  - Full implementation of Claude Sonnet-based case analysis
  - Triggers when cases transition to `upset_bid` classification
  - Extracts: Summary, Financial Deep Dive, Red Flags, Data Confirmation, Deed Book/Page, Defendant Name
  - Database-backed queue with `case_analyses` table
  - Frontend: AIAnalysisSection component on Case Detail page with discrepancy review
  - **Key files:**
    - `analysis/analyzer.py` - Main orchestrator calling Claude API
    - `analysis/prompt_builder.py` - Builds prompts with documents + events
    - `analysis/queue_processor.py` - Processes pending analyses
    - `analysis/models.py` - CaseAnalysis SQLAlchemy model
    - `web_app/api/analysis.py` - API endpoints for fetching/resolving discrepancies
    - `frontend/src/components/AIAnalysisSection.jsx` - React component
    - `migrations/add_case_analyses.sql` - Database migration
- **Bug fixes during testing:**
  - **Upset bid handling:** Include event descriptions in AI prompt (more reliable than OCR for bids)
  - **Bid discrepancy logic:** Only flag when AI value > DB value (DB higher = upset bid already captured)
  - **OCR extraction fix:** Event descriptions now authoritative over OCR bids (fixed $9M phantom bid bug)
    - Root cause: OCR read "M94 512 26.90" as $9,451,226.90 (spaces removed)
    - Fix: Always prefer event description bids over OCR extraction
- **Cases tested:** 1876 (25SP000050-910), 932 (24SP001996-910), 427 (22SP001110-910)
- **Known issues:**
  - AI sometimes misattributes document sources (hallucinated document names)
  - AI confused "TOTAL PAYOFF" with "default_amount" - prompt may need clarification
- **Status:** Feature branch pushed to GitHub, NOT merged to main

### Previous Session Changes (Dec 18 - Session 14)
- **Dashboard UI updates:**
  - Replaced "Current Bid" column with "Max Bid" (shows `our_max_bid` from bid ladder)
  - Changed "Min Next Bid" text color from orange to green (#52c41a)
  - Added `our_max_bid` to upset-bids API response
- **Updated quicklink icons:**
  - Zillow icon: Changed from house to bold blue "Z" (fontWeight 900, Arial Black)
  - PropWire icon: Changed to stylized navy "P" matching their logo (#1E3A5F)
- **Files changed:**
  - `frontend/src/pages/Dashboard.jsx` - Column rename + color changes
  - `frontend/src/assets/ZillowIcon.jsx` - Bold Z icon
  - `frontend/src/assets/PropWireIcon.jsx` - Stylized P icon
  - `web_app/api/cases.py` - Added our_max_bid to upset-bids endpoint

### Previous Session Changes (Dec 18 - Session 13)
- **AUTH_DISABLED toggle for development:**
  - Added `AUTH_DISABLED=true` env var to skip OAuth during local development
  - New `web_app/auth/middleware.py` with `@require_auth` decorator
  - When disabled: `/api/auth/me` returns mock admin user, all endpoints accessible
  - When enabled: Normal Google OAuth flow with whitelist enforcement
  - Applied `@require_auth` to all API endpoints (previously review.py and scheduler/api.py were unprotected)
  - Cleaned up scattered `if not google.authorized:` checks in cases.py
- **Files changed:**
  - `web_app/auth/middleware.py` (NEW) - Centralized auth decorator
  - `web_app/api/routes.py` - Mock user when auth disabled
  - `web_app/api/cases.py` - Use decorator, remove manual checks
  - `web_app/api/admin.py` - Respect AUTH_DISABLED in require_admin
  - `web_app/api/review.py` - Add @require_auth (was unprotected)
  - `scheduler/api.py` - Add @require_auth (was unprotected)
  - `common/config.py` - Add AUTH_DISABLED config

### Previous Session Changes (Dec 18 - Session 12)
- **Claude Vision OCR fallback for handwritten bid amounts:**
  - Root cause: Tesseract OCR completely fails on handwritten text in court forms
  - Case 25SP000165-180 had blank clerk fields + handwritten "$65,000.00 (Credit Bid)"
  - New module: `ocr/vision_ocr.py` - Converts PDF to images, sends to Claude API
  - Integration: `extraction/extractor.py` - `_try_vision_ocr_fallback()` triggers when:
    1. Document is "Report of Sale" or "Upset Bid" type
    2. OCR text has "Amount Bid" label but no dollar amount captured
    3. Regular extraction failed to find bid_amount
  - Extracts: bid_amount, minimum_next_bid, deposit_required, sale_date, deadline_date
  - Cost: ~$0.01-0.03 per document (only runs when Tesseract fails)
  - Model: `claude-sonnet-4-20250514`
- **Pattern fixes for 2 other upset_bid cases:**
  - 25SP000292-310: Added bidirectional deadline pattern (date appears BEFORE label)
  - 25SP000825-310: Fixed "Upsat" OCR typo (`[Uu]ps[ae]t` handles 'a' instead of 'e')
- **Files changed:**
  - `ocr/vision_ocr.py` (NEW) - Claude Vision API integration
  - `extraction/extractor.py` - Vision fallback + pattern fixes
  - `common/config.py` - Added ANTHROPIC_API_KEY config
  - `.env` - Added Anthropic API key (found in upset_bids project)
- **Dependencies:** Added `anthropic` package to venv

### Previous Session Changes (Dec 17 - Session 11)
- **Fixed Zillow link CAPTCHA issue:**
  - Root cause: Manual URL formatting (`123-Main-St-Raleigh-NC`) looked bot-generated
  - Fix: Changed to proper `encodeURIComponent()` with `+` for spaces
  - Before: `https://www.zillow.com/homes/123-Main-St-Raleigh-NC-27612_rb/`
  - After: `https://www.zillow.com/homes/123+Main+St%2C+Raleigh+NC+27612_rb/`
  - File: `frontend/src/utils/urlHelpers.js`
- **Updated NC Courts Portal icon:**
  - Replaced gavel icon with scales of justice (cleaner, more recognizable)
  - File: `frontend/src/assets/GavelIcon.jsx`

### Previous Session Changes (Dec 17 - Session 10)
- **Scheduler catch-up logic:**
  - Root cause: If system boots after 5 AM, daily scrape was missed entirely until next day
  - Fix: Added `check_for_missed_run()` method in `scheduler_service.py`
  - On startup, checks if today is a scheduled day, past scheduled time, and no run today
  - If all conditions met, executes immediately instead of waiting until tomorrow
- **Daily Scrapes page - Acknowledge/Dismiss feature:**
  - Added `acknowledged_at` column to `scrape_logs` table
  - New endpoint: `POST /api/scheduler/acknowledge/<log_id>`
  - Failed scrapes warning now only shows unacknowledged failures
  - Added "Dismiss" button next to "Retry" to acknowledge and hide warnings
- **Fixed task timing for New Case Search:**
  - Root cause: Task was logged "retroactively" after completion, showing 0s duration
  - Fix: Added `log_completed_task()` method to TaskLogger with explicit timestamps
  - Now captures start time before `run_new_case_search()` and end time after
- **Files changed:**
  - `scheduler/scheduler_service.py` - Added catch-up logic
  - `scheduler/api.py` - Added acknowledge endpoint, included acknowledged_at in history
  - `database/models.py` - Added acknowledged_at column to ScrapeLog
  - `scraper/daily_scrape.py` - Added log_completed_task(), fixed Task 1 timing
  - `frontend/src/pages/DailyScrape.jsx` - Added dismiss button, filter acknowledged

### Previous Session Changes (Dec 16 - Session 9)
- **Admin UI: Case Monitor feature:**
  - Added Mode radio buttons to Manual Scrape section: "Date Range Scrape" vs "Case Monitor"
  - Case Monitor options: "Dashboard Cases (upset_bid)" or "All Upcoming Cases"
  - New endpoint `POST /api/admin/monitor` runs `monitor_cases()` with selected classification
  - Results show cases checked, events added, classifications changed, bid updates
- **Fixed bulk approval bug:**
  - Root cause: `approveAllForeclosures()` was called without required `date` parameter
  - Fix: Pass `data.date` to API call in `ReviewQueue.jsx`
- **Fixed NULL classification monitoring gap:**
  - Root cause: Cases with `classification=NULL` were never monitored by `case_monitor.py`
  - These cases missed new sale events (e.g., case 25SP001376-910 had Report of Sale on 12/12 but wasn't detected)
  - Fix: Added `or_(Case.classification.is_(None))` to monitoring query filter
  - 156 NULL classification cases now included in daily monitoring
- **Recovered case 25SP001376-910:**
  - Petition to Sell case with Report of Sale on 12/12/2025
  - Now shows on dashboard: $321,000 bid, deadline 12/26, address 4029 Strickland Farm Road
- **Fixed address extraction issues:**
  - Case 25SP001024-910: Pattern captured garbage text ("Grantors: Brandon S. Roe a married man...")
    - Fix: Added validation to reject addresses containing legal keywords (Grantor, Grantee, married man/woman, etc.)
  - Case 25SP002519-910: Wrong address (Matthews, NC instead of Raleigh)
    - Root cause 1: EVENT_ADDRESS_PATTERN used `.match()` instead of `.search()`
    - Root cause 2: Pattern didn't allow periods in street names (e.g., "W. Lake Anne Drive")
    - Fix: Changed to `.search()` and added `\.` to character class
  - Case 25SP001024-910: Duplicate address with 25SP001017-910
    - Root cause: Court clerical error - Report of Sale PDF had wrong property address
    - Fix: Manually corrected to 5718 Sentinel Drive, Raleigh, NC 27609
- **Address extraction improvements (`extractor.py`):**
  - Added legal keyword validation inside captured addresses (lines 410-425)
  - Changed EVENT_ADDRESS_PATTERN from `.match()` to `.search()` (line 1244)
  - Added period `.` to street name character class for "W." abbreviations (line 1224)

### Previous Session Changes (Dec 16 - Session 8)
- **Fixed bid extraction from event descriptions (case 25SP001906-910):**
  - Root cause: Event descriptions weren't being fully captured (parser stopped at document notices)
  - Fix: Changed `page_parser.py` to continue past "A document is available" lines instead of breaking
  - Added `_find_bid_in_event_descriptions()` in `extractor.py` to extract "Bid Amount $X" from event text
  - Added `update_existing_events_with_descriptions()` in `case_monitor.py` to backfill descriptions
  - Result: Case 25SP001906-910 updated from wrong $8,327.49 to correct $9,830.00
- **Fixed address extraction (case 22SP001110-910):**
  - Root cause 1: Document priority put "Report of Foreclosure Sale" before "Notice of SaleResale"
  - Root cause 2: Address extraction never overwrote existing (even wrong) addresses
  - Fix: Reordered `ADDRESS_DOCUMENT_PRIORITY` - Notice of Sale now highest priority (has explicit "Address of Property:" labels)
  - Fix: Added address quality scoring (0-12 = explicit labels, 13+ = generic patterns)
  - Fix: `update_case_with_extracted_data()` now overwrites addresses when new quality ≤ threshold
  - Tightened `address_of_property` pattern to avoid capturing legal text
  - Result: Case 22SP001110-910 corrected from mailing address to property address
- **Dashboard UI improvements:**
  - Removed "Case Classifications" and "Cases by County" tiles
  - Replaced county dropdown with tabs showing bid counts: "Wake (17)", "Durham (3)", etc.
  - Changed to client-side filtering (all data fetched once)
- **Re-ran extraction on all 36 upset_bid cases:**
  - 3 addresses auto-corrected (typos, wrong county)
  - 4 addresses manually reverted (pattern captured garbage text)

### Previous Session Changes (Dec 15 - Session 7)
- **Fixed stale case reclassification bug:**
  - Root cause: Deadlines stored as midnight (00:00:00) instead of 5 PM courthouse close
  - Case 25SP001706-910 was prematurely moved to closed_sold at 12:51 PM on deadline day
  - Fix: Changed `datetime.min.time()` to `time(17, 0, 0)` in `classifier.py:468`
  - Fix: Updated stale reclassification in `daily_scrape.py` to check if current time > 5 PM on deadline day
- **Fixed Petition to Sell address extraction (case 25SP002123-910):**
  - Root cause: Event descriptions from portal weren't being scraped
  - Added event_description extraction in `page_parser.py` (captures address from "Report of Sale" events)
  - Added event_description saving in `date_range_scrape.py` and `case_monitor.py`
  - Added `_find_address_in_event_descriptions()` in `extractor.py`
  - For Special Proceeding cases, event descriptions are now checked FIRST (more reliable than OCR)
- **Fixed bid extraction bug (case 25SP000133-180):**
  - Root cause: Greedy pattern `offer\s+to\s+purchase[^$]*\$` was matching minimum_next_bid instead of actual bid
  - Fix: Added `(?:was\s+)?` to "property sold for" pattern
  - Fix: Added generic "sold for $X" pattern
  - Fix: Limited greedy pattern to `[^$]{0,200}` chars
- **Dashboard improvements:**
  - Added NC Courts Portal link (gavel icon) in Links column
  - "Back to Cases" button now goes to Dashboard (was All Cases)
  - New icon: `frontend/src/assets/GavelIcon.jsx`

### Previous Session Changes (Dec 15 - Session 6)
- **Zillow QuickLink enrichment (Phase 1):**
  - New utility: `frontend/src/utils/urlHelpers.js` - `formatZillowUrl()` for address-to-URL conversion
  - New icons: `frontend/src/assets/ZillowIcon.jsx`, `PropWireIcon.jsx`
  - Case Detail: Zillow button now active in QuickLinks section (opens Zillow property page)
  - Dashboard: Added "Links" column with 5 icons (Gavel/Zillow active, PropWire/Deed/PropertyInfo disabled "Coming soon")
- **Status:** Merged to main

### Previous Session Changes (Dec 13 - Session 5)
- **Phase 3: Collaboration Features implemented:**
  - Team notes with auto-save (1.5s debounce)
  - Bid ladder editing (Initial, 2nd, Max) with validation
  - PATCH /api/cases/<id> endpoint for collaboration fields
  - useAutoSave hook with save-on-unmount
  - NotesCard component
- **Case Detail page redesign:**
  - Header: title, property address, county, deadline (compact single line)
  - Bid Information: 3-column layout (Current/Min | Sale/Deadline | Our Bids)
  - Notes card on right column
  - Removed redundant Property card
- **Database:** Added 4 columns to cases table (our_initial_bid, our_second_bid, our_max_bid, team_notes)
- **Migration:** `migrations/add_collaboration_fields.sql`

### Previous Session Changes (Dec 13 - Session 4)
- **Root cause analysis of OCR/extraction incompleteness:**
  - Identified 6 root causes for incomplete OCR/extraction
  - 188 documents had file_path but no ocr_text (1.9% of total)
- **Fix 1: OCR retry for insufficient text** (`ocr/processor.py`)
  - Now returns False for <50 chars, allowing retry on subsequent runs
  - Changed extraction failure logging from WARNING to ERROR
- **Fix 2: Extraction tracking** (`database/models.py`, `extraction/extractor.py`)
  - Added `extraction_attempted_at` column to documents table
  - Added `get_documents_needing_extraction()` function
  - Migration: `migrations/add_extraction_tracking.sql`
- **Fix 3: Unconditional OCR tasks** (`scraper/daily_scrape.py`)
  - Removed `cases_processed > 0` condition from Task 1.5
  - OCR now runs even when no new cases found
- **Fix 4: OCR all document types** (`scraper/case_monitor.py`)
  - Now OCRs ALL documents, not just upset_bid/sale types
  - Fixes "unknown_*.pdf" files that were being skipped
- **Fix 5: Replaced bare except blocks** (3 files)
  - Added proper exception handling and logging to 9 bare `except:` blocks
  - `case_monitor.py`, `extractor.py`, `portal_interactions.py`
- **Cleanup:** Deleted 68 orphaned document records (files never existed on disk)
- **Result:** All 37 upset_bid cases have 100% complete data and OCR coverage

### Previous Session Changes (Dec 13 - Session 3)
- **Fixed Daily Scrape duration bug:**
  - Root cause: Timezone mismatch - `started_at` used PostgreSQL local time, `completed_at` used Python UTC
  - Was showing 5h duration for 15min scrapes due to EST/UTC offset
  - Fix: Changed `datetime.utcnow()` to `datetime.now()` in `date_range_scrape.py`
- **Added task-level tracking for daily scrapes:**
  - New `scrape_log_tasks` table tracks individual tasks within each scrape
  - Tasks logged: new_case_search, ocr_after_search, case_monitoring, ocr_after_monitoring, upset_bid_validation, stale_reclassification, self_diagnosis
  - Each task records: items_checked, items_found, items_processed, duration, status
  - `TaskLogger` class in `daily_scrape.py` handles logging
  - API `/api/scheduler/history` now returns `tasks` array for each log
  - Frontend Daily Scrape tab has expandable rows showing task breakdown
- **UI cleanup:** Renamed "Settings" tab to "Admin"

### Previous Session Changes (Dec 13 - Session 2)
- **Admin Tab implemented (admin only):**
  - Manual Scrape section: date range picker, county checkboxes, party name filter
  - User Management section: add/edit/delete users, role-based access (Admin/User)
  - Whitelist auth: users must be added before they can log in
  - `ADMIN_EMAIL` env var seeds first admin on startup
- **Backend changes:**
  - `role` column added to users table
  - `/api/admin/users` CRUD endpoints
  - `/api/admin/scrape` endpoint for manual scraping
  - `party_name` parameter added to DateRangeScraper
- **Review Queue cleanup:** Removed unused date selector

### Previous Session Changes (Dec 13 - Session 1)
- **Self-diagnosis system for upset_bid cases:**
  - Three-tier healing approach: re-extract → re-OCR → re-scrape
  - Runs as Task 5 in `daily_scrape.py` after all scraping/monitoring
  - Detects missing critical fields: sale_date, upset_deadline, property_address, current_bid
  - Successfully healed 2 cases with missing sale_date on first run

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
| upcoming | 1,464 | Foreclosure initiated, no sale |
| upset_bid | 37 | Sale occurred, within 10-day bid period |
| blocked | 69 | Bankruptcy/stay in effect |
| closed_sold | 358 | Past upset period |
| closed_dismissed | 68 | Case dismissed |
| NULL | 156 | Unclassified (non-foreclosure Special Proceedings) |

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
- `ocr/` - PDF text extraction (Tesseract + Claude Vision fallback for handwritten text)
- `analysis/` - Claude AI analysis (haiku model)

### Key Files
- `scraper/case_monitor.py` - Monitors existing cases via direct URLs (no CAPTCHA)
- `scraper/daily_scrape.py` - Orchestrates daily tasks (3-day lookback on Mondays)
- `scraper/self_diagnosis.py` - Auto-healing for upset_bid cases with missing data
- `scraper/page_parser.py` - Day-1 detection indicators + exclusions
- `extraction/classifier.py` - Case status classification
- `extraction/extractor.py` - Regex extraction from OCR text + Claude Vision fallback
- `ocr/vision_ocr.py` - Claude Vision API for handwritten text extraction
- `common/business_days.py` - NC court holiday calendar for deadline calculation
- `web_app/api/admin.py` - Admin endpoints for user management and manual scraping
- `scripts/reevaluate_skipped.py` - Re-check skipped cases against updated indicators
- `scripts/download_missing_documents.py` - Downloads docs for cases with 0 documents

### Database Tables
`cases`, `case_events`, `parties`, `hearings`, `documents`, `scrape_logs`, `scrape_log_tasks`, `scheduler_config`, `users`

## Critical Design Decisions

1. **Deadlines from events ONLY** - PDF OCR unreliable for handwritten dates. Use `event_date + 10 business days`
2. **NC G.S. 45-21.27** - If 10th day falls on weekend/holiday, extends to next business day
3. **PDF extraction** - Only used for bid amounts, NOT deadlines
4. **Headless=False** - Angular pages fail in headless mode
5. **Documents linked to events** - `documents.event_id` foreign key ties PDFs to case_events
6. **Address extraction patterns** - Comma-optional patterns for OCR text (handles variations)

## Environment Variables (.env)
`DATABASE_URL`, `CAPSOLVER_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `FLASK_SECRET_KEY`, `ADMIN_EMAIL`, `AUTH_DISABLED`

## Frontend Development

```bash
# Create feature worktree
./scripts/dev_worktree.sh create my-feature
cd .worktrees/my-feature/frontend
npm install && npm run dev -- --port 5174
```

## Next Priorities
1. PropWire enrichment (next quicklink)
2. County Deed enrichment
3. County Property Info enrichment

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
