# Session History

Detailed session-by-session history for NC Foreclosures project. This file preserves context for debugging and understanding past decisions.

---

## Session 34 (Jan 22, 2026) - Resale Case Extraction Fix

**Resale case extraction fix (comprehensive):**
- **Problem:** Resale cases (sale set aside, new sale occurred) had stale bid/deadline data from voided sales
- Case 23SP003301-910 had 3 sales (Apr 2024, Feb 2025, Jan 2026) - extraction was reading old documents
- **Fix 1:** `extract_all_from_case()` - Added sale_date filtering to skip documents dated before current sale
- **Fix 2:** `_try_vision_ocr_fallback()` - Added sale_date filtering to skip Vision OCR on old documents
- **Fix 3:** Removed OCR deadline extraction entirely - deadlines must ONLY come from event dates
- **Fix 4:** Skip "unknown__*.pdf" files (NULL dates) when sale_date filtering is active

**Bid pattern fix:**
- Event descriptions like "$294,275.00 Billy Finch" weren't being matched
- Added pattern: `^\$\s*([\d,]+\.\d{2})\s+[A-Z]` for amount at start followed by name
- Ensures event descriptions (authoritative) are used instead of Vision OCR fallback

**Manual price fixes:**
- 23SP003301-910: $9,210 → $22,253 (resale case, old doc extracted)
- 25SP000031-420: $894,275 → $294,275 (Vision OCR misread 2 as 8)
- 25SP000219-420: $2,735 → $60,000 (deposit extracted instead of bid)
- 25SP000383-670: NULL → $113,800 (Commissioner sale, empty event description)

**Files modified:**
- `extraction/extractor.py` - sale_date filtering, bid pattern, removed OCR deadline extraction

---

## Session 33 (Jan 21, 2026) - Est. Rehab Cost & Header Redesign

**Est. Rehab Cost field added:**
- New field in Bid Information tile below Est. Sale Price
- Currency input with auto-save (like other bid fields)
- Database column added: `cases.estimated_rehab_cost` (DECIMAL 12,2)

**Profit calculation updated:**
- Now: `Est. Sale Price - Our Max Bid - Est. Rehab Cost`
- Updated in all 3 locations in `web_app/api/cases.py`

**Case Detail header redesign:**
- Property address is now the prominent header (Title level 4)
- Removed case style/type title (was "FORECLOSURE OF A DEED OF TRUST Ida Delaney")
- Case number and county remain in subtitle

**Files modified:**
- `frontend/src/pages/CaseDetail.jsx` - Header redesign, Est. Rehab Cost state/input/auto-save
- `database/models.py` - Added estimated_rehab_cost column
- `web_app/api/cases.py` - Added estimated_rehab_cost to GET/PATCH, updated profit calc

---

## Session 32 (Jan 20, 2026) - Resale Extraction Fix & Weekly Scan

**Resale bid extraction bug fixed:**
- **Root cause:** `_find_bid_in_event_descriptions()` in `extractor.py` searched ALL events without filtering by `sale_date`
- For resale cases (where sale was set aside), this caused old bids from voided sales to be extracted
- Cases 24SP001381-910 and 23SP003301-910 showed EXPIRED deadlines because extraction overwrote correct deadline
- **Fix:** Added `sale_date` filtering to only search events from current sale cycle

**Task 9: Weekly closed_sold scan:**
- New task runs every Friday (scheduler only runs Mon-Fri)
- Scans ALL closed_sold cases for new set-aside events
- Complements daily grace period monitoring (Task 7) and daily set-aside monitoring (Task 8)
- Ensures no set-aside events slip through after the 5-day grace period

**Tailscale partner access discussion:**
- Explained Tailscale network access vs application auth distinction
- Sharing machine gives network connectivity; Google OAuth whitelist protects app
- Documented ACL option for port-level restrictions if needed

**Files modified:**
- `extraction/extractor.py` - Added sale_date filtering to `_find_bid_in_event_descriptions()`
- `scraper/daily_scrape.py` - Added Task 9 (run_closed_sold_weekly_scan) with Friday check

---

## Session 31 (Jan 19, 2026) - Chronology Audit

**Chronology audit - 4 bugs fixed:**
- `case_monitor.py`: `extract_bid_amount()` was using `max(amounts)` instead of most recent - now returns first match (page shows newest-first)
- `extractor.py`: `_find_address_in_event_descriptions()` missing ORDER BY - added `ORDER BY event_date DESC, id DESC`
- `extractor.py`: `update_case_with_extracted_data()` used `>` comparison for bids - changed to update if different (trusts extraction chronology)
- `extractor.py`: `extract_all_from_case()` document iteration without ORDER BY - added `ORDER BY created_at DESC, id DESC`

**Interest validation race condition fix:**
- Bug: Clicking "Yes - Interested" after filling bid ladder fields showed "Complete Est. Sale Price and Bid Ladder" error
- Root cause: Backend read stale database values instead of current form values
- Fix: Frontend now sends current form values with interest status change request

---

## Session 30 (Jan 16, 2026) - Dashboard Interest Filter

**Dashboard interest status filter:**
- New filter row with All/Interested/Needs Review options
- Counts update based on selected county
- Persists in URL (`?interest=needs_review`)

**Deed URL fixes for Logan Systems counties:**
- Lee and Chatham deed links now point to disclaimer pages
- Direct search pages caused errors

**Dashboard county tab persistence:**
- Navigating to case detail and back now preserves county tab selection via URL params

---

## Session 29 (Jan 16, 2026) - Chatham Enrichment Fix

**Chatham County enrichment fix:**
- Scraper now searches with full address (e.g., "88 Maple Springs") instead of just street number
- Fixed false positive matches

**Bid ladder unmount save fix:**
- Fixed race condition where clearing bid fields and quickly navigating away lost changes

---

## Session 28 (Jan 16, 2026) - Bid Field Clearing

**Bid field clearing fix:**
- Users can now delete bid data and it stays empty (was reverting)

**Address extraction cleanup:**
- Strip "commonly known as" prefix
- Truncate after ZIP code

**Set-aside monitoring moved to daily:**
- Task 8 now runs daily (was Friday-only)

---

## Session 27 (Jan 12, 2026) - Interest Tracking Feature

**Interest Tracking - Complete implementation:**
- Track whether cases have been manually analyzed with "Interested? Yes/No" decision
- Three-state system: Not Reviewed → Interested → Not Interested

**Database:**
- Added `interest_status` column (VARCHAR(20)) to `cases` table
- Values: NULL (not reviewed), 'interested', 'not_interested'
- Added index `idx_cases_interest_status` for filtering

**API Validation:**
- "Yes" (Interested) requires: Est. Sale Price + Our Initial + Our 2nd + Our Max bid fields
- "No" (Not Interested) requires: Team Notes must have text content
- Empty string clears status back to NULL (not reviewed)

**Dashboard:**
- New "Review" column before Links
- Hurricane warning flag icon (custom SVG - red flag, black square, wind-blown) = not reviewed
- Green check = interested
- Red X = not interested

**Case Detail:**
- "Analysis Decision" card below Team Notes
- Yes/No toggle buttons (green/red when active)
- Click active button to clear (revert to not reviewed)
- Validation error messages display below buttons

**Files created/modified:**
- `migrations/add_interest_status.sql` - Database migration
- `database/models.py` - Added interest_status field
- `web_app/api/cases.py` - Validation logic + response updates
- `frontend/src/assets/HurricaneWarningIcon.jsx` - Custom SVG component
- `frontend/src/pages/Dashboard.jsx` - Review column
- `frontend/src/pages/CaseDetail.jsx` - Analysis Decision card

**Implementation approach:** Used superpowers subagent-driven-development with 9 tasks, code review after each task.

---

## Session 24 (Dec 23, 2025) - Grace Period Monitoring

**Grace Period Monitoring for Closed Sold Cases:**
- **Root cause:** Case 25SP002519-910 had upset bid filed 12/22 but system missed it - case was already `closed_sold`
- **Problem:** Once classified as `closed_sold`, cases were never monitored again
- **Solution:** 5-day grace period after classification to catch late-filed events
- New `closed_sold_at` timestamp column tracks when cases transition
- Task 7 in daily_scrape.py monitors grace period cases with full re-monitor
- If new sale events detected, case automatically reclassifies back to `upset_bid`

**Written Month Date Format Support:**
- **Root cause:** Case 25SP002755-910 (Shield Circle) had no deadline - OCR showed "January 2, 2026" but patterns only handled "1/2/2026"
- Added pattern for written month format in UPSET_DEADLINE_PATTERNS
- Updated `extract_upset_deadline()` to parse: %B %d, %Y, %B %d %Y, %b %d, %Y, %b %d %Y

**Cases fixed:**
- 25SP002519-910 (Lake Anne Drive): Added 2 new events, new party (Kay York), reclassified to upset_bid, deadline Jan 2, 2026, bid $475k
- 25SP002755-910 (Shield Circle): Set deadline Jan 2, 2026, sale_date 12/22/2025

---

## Session 23 (Dec 22, 2025) - Chatham County RE Enrichment

**Chatham County RE Enrichment - Fully implemented:**
- DEVNET wEdge portal at `chathamnc.devnetwedge.com`
- **Simplest implementation:** HTTP requests + BeautifulSoup (no Playwright needed)
- Search URL: `https://chathamnc.devnetwedge.com/search/quick?q={street_number}`
- Property URL: `https://chathamnc.devnetwedge.com/parcel/view/{parcel_id}/2025`
- Parcel ID format: 7 digits (e.g., `0074237`)
- Search strategy: Query by street number only, filter results by street name match

**Data fix:**
- Case 25SP000165-180: Corrected address from hearing location (40 East Chatham Street) to actual property (4902 Devils Tramping Ground Rd, Bear Creek)

**Test results:** 2/2 Chatham County upset_bid cases enriched

---

## Session 22 (Dec 22, 2025) - Orange County RE Enrichment

**Orange County RE Enrichment - Fully implemented:**
- Spatialest portal at `property.spatialest.com/nc/orange/`
- Playwright automation: Type address in search combobox → Click Search
- Portal auto-navigates to property page for single matches
- **Key insight:** Portal is SPA - extracts Parcel ID from page content (not URL)
- Direct URL format: `https://property.spatialest.com/nc/orange/#/property/{10-digit-parcel-id}`
- Added street name cleanup to handle addresses without comma before city

**Test results:** 2/2 Orange County upset_bid cases enriched

---

## Session 21 (Dec 22, 2025) - Lee County RE Enrichment

**Lee County RE Enrichment - Fully implemented:**
- Tyler Technologies portal at `taxaccess.leecountync.gov`
- Uses role-based Playwright locators (`get_by_role`) for form fields
- **Direction dropdown handling:** Addresses with N/S/E/W prefix use separate `-DIR-` dropdown
  - "103 W Harrington Ave" → street_number=103, direction=WEST, street_name=Harrington
- Extracts 12-digit parcel ID directly from search results (no click-through needed)
- Session-based URLs stored (portal doesn't support direct parcel linking)

**Key fixes:** Fixed county code from '530' to '520', changed text extraction method, added wait for dynamic results

---

## Session 20 (Dec 22, 2025) - Durham County RE Enrichment

**Durham County RE Enrichment:**
- New `enrichments/durham_re/` module with Playwright browser automation
- Searches Durham Tax/CAMA portal (`taxcama.dconc.gov`) by address
- Uses headless Chromium, clicks "Location Address" tab, handles page redirect
- Extracts `PARCELPK` from property link, captures final PropertySummary URL
- 6/7 Durham upset_bid cases enriched (1 case has invalid address)

---

## Session 19 (Dec 21, 2025) - County Router & Wake RE Fixes

**County Router for Enrichments:**
- Added `enrichments/router.py` to dispatch to county-specific enrichers
- Routes based on case_number suffix (e.g., `-910` → Wake, `-310` → Durham)
- Returns `skipped: True` for counties without implemented enrichers

**Wake RE Enrichment - 18/18 cases now enriched:**
- Fixed address extraction bug: Two-column OCR bleed captured "Credit Union" from adjacent column
- Fixed same account_id matching: Condos with multiple rows now recognized as single match
- Fixed malformed addresses: Parser now detects city names merged with street
- Added two-step AddressSearch for directional prefixes (N/S/E/W/NE/NW/SE/SW)

---

## Session 18 (Dec 19, 2025) - AI Analysis Module Merged

**AI Analysis Module merged to main:**
- Enhanced prompt with comprehensive 4-section analysis structure:
  - I. Executive Summary (4-6 sentence overview)
  - II. Analysis of Parties (plaintiff/defendant in 2-column layout)
  - III. Legal & Procedural Analysis (statute citations, compliance review)
  - IV. Conclusion & Key Takeaways (investment considerations)
- Removed chronological timeline (too verbose per user feedback)
- Added NC foreclosure statute references (G.S. 45-21.16 through 45-21.33)
- Increased max_tokens to 8192 for longer responses
- Cost: ~$0.31 per case

**Parcel ID discovery:** Found parcel IDs in 1,033+ documents (potential for QuickLinks integration)

---

## Session 17 (Dec 19, 2025) - Case Detail Layout Update

- Bid Information and Team Notes now side-by-side in same row
- Team Notes card height matches Bid Information card
- AI Analysis section moved directly under those two tiles
- Parties/Contacts/Events pushed below AI Analysis

---

## Session 16 (Dec 19, 2025) - Parser Bug Fix & Case Recovery

**Root cause analysis: Case 25SP001804-910 missing from dashboard**
- Case was in `skipped_cases` table, dismissed on Dec 12
- New "Report of Sale" event added Dec 18 - but dismissed cases are never re-checked
- **Root cause:** Parser bug - event types split across HTML elements weren't captured
  - Portal rendered: `<div>Order</div><div>for Sale of Ward's Real Property</div>`
  - Parser saw "Order" (too short) + "for Sale..." (lowercase) → `event_type = NULL`
- **Impact:** 3,118 events with NULL event_type across 964 cases

**Parser fix:** Added fallback logic to concatenate adjacent short lines that form split event types

**Backfill completed:** Re-parsed 959 cases, fixed 2,411 events (78% of affected)

**Cases recovered:** 25SP001804-910 → `upset_bid`, 25SP002745-910 → `upcoming`

---

## Session 15 (Dec 19, 2025) - AI Analysis Module (Feature Branch)

**AI Analysis Module (feature/ai-analysis branch):**
- Full implementation of Claude Sonnet-based case analysis
- Triggers when cases transition to `upset_bid` classification
- Extracts: Summary, Financial Deep Dive, Red Flags, Data Confirmation, Deed Book/Page, Defendant Name
- Database-backed queue with `case_analyses` table
- Frontend: AIAnalysisSection component on Case Detail page

**Bug fixes during testing:**
- Upset bid handling: Include event descriptions in AI prompt
- Bid discrepancy logic: Only flag when AI value > DB value
- OCR extraction fix: Event descriptions now authoritative over OCR bids

---

## Session 14 (Dec 18, 2025) - Dashboard UI Updates

- Replaced "Current Bid" column with "Max Bid" (shows `our_max_bid` from bid ladder)
- Changed "Min Next Bid" text color from orange to green (#52c41a)
- Updated quicklink icons: Zillow → bold blue "Z", PropWire → stylized navy "P"

---

## Session 13 (Dec 18, 2025) - AUTH_DISABLED Toggle

**AUTH_DISABLED toggle for development:**
- Added `AUTH_DISABLED=true` env var to skip OAuth during local development
- New `web_app/auth/middleware.py` with `@require_auth` decorator
- When disabled: `/api/auth/me` returns mock admin user, all endpoints accessible
- Applied `@require_auth` to all API endpoints (previously some were unprotected)

---

## Session 12 (Dec 18, 2025) - Claude Vision OCR Fallback

**Claude Vision OCR fallback for handwritten bid amounts:**
- Root cause: Tesseract OCR completely fails on handwritten text in court forms
- Case 25SP000165-180 had blank clerk fields + handwritten "$65,000.00 (Credit Bid)"
- New module: `ocr/vision_ocr.py` - Converts PDF to images, sends to Claude API
- Triggers when document is "Report of Sale"/"Upset Bid" type and OCR text has label but no amount
- Cost: ~$0.01-0.03 per document (only runs when Tesseract fails)

**Pattern fixes:**
- 25SP000292-310: Added bidirectional deadline pattern (date appears BEFORE label)
- 25SP000825-310: Fixed "Upsat" OCR typo (`[Uu]ps[ae]t` handles 'a' instead of 'e')

---

## Session 11 (Dec 17, 2025) - Zillow Link Fix & Icon Update

**Fixed Zillow link CAPTCHA issue:**
- Root cause: Manual URL formatting (`123-Main-St-Raleigh-NC`) looked bot-generated
- Fix: Changed to proper `encodeURIComponent()` with `+` for spaces

**Updated NC Courts Portal icon:** Replaced gavel icon with scales of justice

---

## Session 10 (Dec 17, 2025) - Scheduler Catch-up Logic

**Scheduler catch-up logic:**
- Root cause: If system boots after 5 AM, daily scrape was missed entirely until next day
- Fix: Added `check_for_missed_run()` method in `scheduler_service.py`
- On startup, checks if today is a scheduled day, past scheduled time, and no run today
- If all conditions met, executes immediately instead of waiting until tomorrow

**Daily Scrapes page - Acknowledge/Dismiss feature:**
- Added `acknowledged_at` column to `scrape_logs` table
- Failed scrapes warning now only shows unacknowledged failures
- Added "Dismiss" button next to "Retry"

---

## Session 9 (Dec 16, 2025) - Admin UI & Bug Fixes

**Admin UI: Case Monitor feature:**
- Added Mode radio buttons: "Date Range Scrape" vs "Case Monitor"
- Case Monitor options: "Dashboard Cases (upset_bid)" or "All Upcoming Cases"
- New endpoint `POST /api/admin/monitor`

**Fixed NULL classification monitoring gap:**
- Root cause: Cases with `classification=NULL` were never monitored
- Fix: Added `or_(Case.classification.is_(None))` to monitoring query filter
- 156 NULL classification cases now included in daily monitoring

**Fixed address extraction issues:** Added legal keyword validation, fixed pattern matching

---

## Session 8 (Dec 16, 2025) - Bid & Address Extraction Fixes

**Fixed bid extraction from event descriptions (case 25SP001906-910):**
- Root cause: Event descriptions weren't being fully captured
- Fix: Changed `page_parser.py` to continue past "A document is available" lines
- Added `_find_bid_in_event_descriptions()` in `extractor.py`

**Fixed address extraction (case 22SP001110-910):**
- Reordered `ADDRESS_DOCUMENT_PRIORITY` - Notice of Sale now highest priority
- Added address quality scoring (0-12 = explicit labels, 13+ = generic patterns)

**Dashboard UI improvements:**
- Removed "Case Classifications" and "Cases by County" tiles
- Replaced county dropdown with tabs showing bid counts

---

## Session 7 (Dec 15, 2025) - Stale Reclassification & Petition to Sell

**Fixed stale case reclassification bug:**
- Root cause: Deadlines stored as midnight (00:00:00) instead of 5 PM courthouse close
- Fix: Changed `datetime.min.time()` to `time(17, 0, 0)` in `classifier.py`

**Fixed Petition to Sell address extraction:**
- Added event_description extraction in `page_parser.py`
- For Special Proceeding cases, event descriptions checked FIRST

**Dashboard improvements:** Added NC Courts Portal link (gavel icon)

---

## Session 6 (Dec 15, 2025) - Zillow QuickLink

**Zillow QuickLink enrichment (Phase 1):**
- New utility: `frontend/src/utils/urlHelpers.js` - `formatZillowUrl()`
- New icons: `ZillowIcon.jsx`, `PropWireIcon.jsx`
- Dashboard: Added "Links" column with 5 icons

---

## Session 5 (Dec 13, 2025) - Collaboration Features

**Phase 3: Collaboration Features implemented:**
- Team notes with auto-save (1.5s debounce)
- Bid ladder editing (Initial, 2nd, Max) with validation
- PATCH /api/cases/<id> endpoint for collaboration fields
- useAutoSave hook with save-on-unmount
- NotesCard component

**Case Detail page redesign:**
- Header: title, property address, county, deadline (compact single line)
- Bid Information: 3-column layout
- Notes card on right column

---

## Session 4 (Dec 13, 2025) - OCR/Extraction Pipeline Reliability

**Root Cause Analysis:** Identified 6 root causes for incomplete OCR/extraction

| Fix | Change |
|-----|--------|
| 1 | OCR returns False for <50 chars, allowing retry |
| 2 | Added `extraction_attempted_at` tracking |
| 3 | Removed `cases_processed > 0` condition from Task 1.5 |
| 4 | OCR all documents, not just upset_bid/sale |
| 5 | Replaced 9 bare `except:` with proper logging |
| 6 | Added `get_documents_needing_extraction()` |

**Results:** All 37 upset_bid cases: 100% complete data and OCR coverage

---

## Session 3 (Dec 13, 2025) - Daily Scrape Tracking

**Fixed Daily Scrape duration bug:**
- Root cause: Timezone mismatch - `started_at` used PostgreSQL local time, `completed_at` used Python UTC
- Fix: Changed `datetime.utcnow()` to `datetime.now()`

**Added task-level tracking for daily scrapes:**
- New `scrape_log_tasks` table tracks individual tasks
- Each task records: items_checked, items_found, items_processed, duration, status

---

## Session 2 (Dec 13, 2025) - Admin Tab

**Admin Tab implemented (admin only):**
- Manual Scrape section: date range picker, county checkboxes, party name filter
- User Management section: add/edit/delete users, role-based access
- Whitelist auth: users must be added before they can log in
- `ADMIN_EMAIL` env var seeds first admin on startup

---

## Session 1 (Dec 13, 2025) - Self-Diagnosis System

**Self-diagnosis system for upset_bid cases:**
- Three-tier healing approach: re-extract → re-OCR → re-scrape
- Runs as Task 5 in `daily_scrape.py` after all scraping/monitoring
- Detects missing critical fields: sale_date, upset_deadline, property_address, current_bid
- Successfully healed 2 cases with missing sale_date on first run

---

## Earlier Sessions (Dec 11-12, 2025)

**Historical backfill completed:** 2020-01-01 to 2025-11-24 (426 chunks, 71 months × 6 counties)
- Added 353 new cases (1,770 → 2,123 total)

**Unified scraper architecture:**
- Deleted `initial_scrape.py`, `batch_initial_scrape.py`, `parallel_batch_scrape.py`
- New scrapers: `batch_scrape.py` and `parallel_scrape.py` with configurable chunking

**Classifier defense-in-depth:** Added `SALE_CONFIRMED_EVENTS` patterns

**Fixed extraction pipeline for monitored cases**

---

## Foundation Sessions (Nov 24 - Dec 10, 2025)

- PostgreSQL + SQLAlchemy setup
- Playwright scraper with CapSolver CAPTCHA
- Kendo UI Grid parsing
- All 6 counties scraped (2020-2025)
- OCR and extraction modules
- 5 classification states defined
- Claude API integration (haiku model)
- React + Vite + Ant Design frontend
- Flask API with Google OAuth
- Scheduler service (5 AM Mon-Fri)
- 1,716 initial cases
