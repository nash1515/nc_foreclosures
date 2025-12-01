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
**Current Branch:** `feature/phase1-foundation`

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
6. Implement daily scrape functionality (include monitoring of `blocked` cases)
7. Implement enrichment module (Zillow, county records, tax values)
8. Analyze `closed_sold` cases (91) for bidding strategy patterns by county

### Recent Updates (Dec 1, 2025) - Session 9 Continued (Classification Cleanup)
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

```bash
# Start VPN (from ~/frootvpn directory)
# Can use any US server (Virginia, California, Florida, Georgia, Illinois, New York)
# or other nearby servers with good latency
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

### Running the Scraper

**Prerequisites:**
1. VPN connected (see above)
2. PostgreSQL running: `sudo service postgresql start`
3. CapSolver API key in `.env`

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

## Architecture Overview

### Database Schema
- `cases` - Main foreclosure case information
- `case_events` - Timeline of case events
- `documents` - PDF files and OCR text
- `scrape_logs` - Audit trail of scraping activity
- `user_notes` - User annotations (for web app)

### Module Structure
- `common/` - Shared utilities (config, logging, county codes)
- `database/` - ORM models and connection management
- `scraper/` - Web scraping (VPN, CAPTCHA, Playwright)
- `ocr/` - PDF processing (Phase 2)
- `analysis/` - AI analysis (Phase 3)
- `web_app/` - Flask app (Phase 4)
- `tests/` - Integration tests

### Key Files
- `database/schema.sql` - PostgreSQL schema
- `database/models.py` - SQLAlchemy ORM models
- `scraper/initial_scrape.py` - Main scraper script
- `scraper/vpn_manager.py` - VPN verification
- `scraper/captcha_solver.py` - reCAPTCHA solving (CapSolver API)
- `scraper/page_parser.py` - Kendo UI Grid HTML parsing
- `scraper/portal_interactions.py` - Form filling and navigation
- `scraper/portal_selectors.py` - CSS selectors for portal elements

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

## Documentation

- `docs/KENDO_GRID_FIXES.md` - Kendo UI implementation details (Nov 24, 2025)
- `docs/SESSION_SUMMARY.md` - Previous session summary
- `docs/SETUP.md` - Detailed setup instructions
- `docs/plans/2025-11-24-nc-foreclosures-architecture-design.md` - Full architecture
- `docs/plans/2025-11-24-phase1-foundation-implementation.md` - Phase 1 plan
- `PROJECT_REQUIREMENTS.md` - Original requirements
