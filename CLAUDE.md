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
**Phase 3 Initial Scrape:** 🔄 In Progress (2020-2021 done, 2022-2025 pending)
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

### Scrape Progress (as of Nov 25, 2025)

| Year | Wake | Durham | Harnett | Lee | Orange | Chatham | Total |
|------|------|--------|---------|-----|--------|---------|-------|
| 2020 | 102 | 10 | 8 | 4 | 6 | SKIP | 130 |
| 2021 | 61 | 8 | 7 | 6 | 1 | SKIP | 83 |
| **Total** | **163** | **18** | **15** | **10** | **7** | **0** | **213** |

**Note:** Chatham County temporarily skipped due to portal issues.

### Next Steps
1. ~~Run full initial scrape for all 6 counties~~ (2020-2021 done)
2. Continue scraping 2022-2025
3. Retry failed date ranges (see `data/scrape_failures/ALL_MISSING_TIMEFRAMES.md`)
4. Investigate Chatham County portal issues
5. Implement daily scrape functionality
6. Implement enrichment module (Zillow, county records, tax values)

### Recent Updates (Nov 25, 2025) - Session 6
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
- **Scrape Results:**
  - 2020: 130 foreclosure cases (5 counties)
  - 2021: 83 foreclosure cases (5 counties)
  - Total: 213 foreclosures in database
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
cd ~/frootvpn
sudo openvpn --config "United States - Virginia.ovpn" --auth-user-pass auth.txt --daemon --log /tmp/openvpn.log

# Verify VPN is connected
curl ifconfig.me  # Should show 74.115.214.142 (not baseline 136.61.20.173)

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

1. **Chatham County Portal Issues:** All searches for Chatham County fail - even manual searches have problems. Temporarily excluded from scraping.
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
