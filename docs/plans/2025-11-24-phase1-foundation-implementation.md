# Phase 1 Foundation - Implementation Plan

**Date:** 2025-11-24
**Branch:** feature/phase1-foundation
**Worktree:** `.worktrees/phase1-foundation/`

## Objective

Build the foundation for the NC Foreclosures system:
- PostgreSQL database with schema
- Basic web scraper using Playwright
- VPN verification before scraping
- CapSolver reCAPTCHA integration
- Test on single county, single month sample
- Basic data extraction (no OCR or AI yet)

## Prerequisites

- PostgreSQL installed and running
- Python 3.12
- FROOT VPN configured
- CapSolver API key: `CAP-06FF6F96A738937699FA99040C8565B3D62AB676B37CC6ECB99DDC955F22E4E2`

## Tasks

### Task 1: Project Structure Setup

**Goal:** Create the monorepo folder structure and configuration files.

**Steps:**

1. Create module directories:
```bash
mkdir -p scraper database ocr analysis web_app common data/pdfs
```

2. Create `requirements.txt` with initial dependencies:
```
playwright==1.40.0
playwright-stealth==1.0.0
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
python-dotenv==1.0.0
capsolver-python==1.1.0
requests==2.31.0
beautifulsoup4==4.12.2
```

3. Create `.env` file (not committed):
```
DATABASE_URL=postgresql://nc_user:nc_password@localhost/nc_foreclosures
CAPSOLVER_API_KEY=CAP-06FF6F96A738937699FA99040C8565B3D62AB676B37CC6ECB99DDC955F22E4E2
VPN_BASELINE_IP=<get from ifconfig.me when VPN off>
PDF_STORAGE_PATH=./data/pdfs
LOG_LEVEL=INFO
```

4. Create `common/config.py` to load environment variables
5. Create `common/logger.py` for standardized logging

**Files created:**
- `requirements.txt`
- `.env.example` (template for .env)
- `common/config.py`
- `common/logger.py`
- `common/__init__.py`

**Verification:**
- All directories exist
- Can import from common modules
- Config loads environment variables correctly

---

### Task 2: PostgreSQL Database Setup

**Goal:** Install PostgreSQL, create database and schema with all tables.

**Steps:**

1. Install PostgreSQL on WSL:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo service postgresql start
```

2. Create database and user:
```bash
sudo -u postgres psql
CREATE DATABASE nc_foreclosures;
CREATE USER nc_user WITH PASSWORD 'nc_password';
GRANT ALL PRIVILEGES ON DATABASE nc_foreclosures TO nc_user;
\q
```

3. Create `database/schema.sql` with table definitions:
   - `cases` table with all fields from architecture
   - `case_events` table
   - `documents` table
   - `scrape_logs` table
   - `user_notes` table
   - Indexes on: case_number, county_code, classification
   - Full-text index on documents.ocr_text

4. Create `database/models.py` with SQLAlchemy ORM models matching schema

5. Create `database/connection.py`:
   - Database connection pool
   - Session management
   - Helper functions (get_session, close_session)

6. Create `database/init_db.py` script to:
   - Run schema.sql
   - Create tables if they don't exist
   - Verify connection

**Files created:**
- `database/schema.sql`
- `database/models.py`
- `database/connection.py`
- `database/init_db.py`
- `database/__init__.py`

**Verification:**
```bash
python database/init_db.py
# Should show: Database initialized successfully
```

```sql
psql -U nc_user -d nc_foreclosures -c "\dt"
# Should list all 5 tables
```

---

### Task 3: VPN Manager

**Goal:** Implement VPN connection verification before scraping.

**Steps:**

1. Create `scraper/vpn_manager.py` with:
   - `get_current_ip()` - fetches current public IP from ifconfig.me
   - `is_vpn_connected()` - compares current IP to baseline (from .env)
   - `verify_vpn_or_exit()` - checks VPN, exits if not connected
   - Logging for all checks

2. Test functionality:
   - Get baseline IP with VPN off, save to .env
   - Turn VPN on
   - Run verification - should pass
   - Turn VPN off
   - Run verification - should fail with clear error

**Files created:**
- `scraper/vpn_manager.py`
- `scraper/__init__.py`

**Verification:**
```bash
# With VPN on
python -c "from scraper.vpn_manager import verify_vpn_or_exit; verify_vpn_or_exit()"
# Should print: VPN verified, IP: <vpn-ip>

# With VPN off
python -c "from scraper.vpn_manager import verify_vpn_or_exit; verify_vpn_or_exit()"
# Should exit with error: VPN not connected! Current IP matches baseline.
```

---

### Task 4: CapSolver Integration

**Goal:** Integrate CapSolver API to solve reCAPTCHA.

**Steps:**

1. Install Playwright browsers:
```bash
playwright install chromium
```

2. Create `scraper/captcha_solver.py` with:
   - `solve_recaptcha(page_url, site_key)` function
   - Uses capsolver-python SDK
   - Submits task to CapSolver API
   - Polls for solution
   - Returns captcha token
   - Error handling and retries (max 3 attempts)
   - Logging

3. Create test script `scraper/test_captcha.py`:
   - Opens a test reCAPTCHA page
   - Calls solve_recaptcha
   - Injects token
   - Verifies success

**Files created:**
- `scraper/captcha_solver.py`
- `scraper/test_captcha.py`

**Verification:**
```bash
python scraper/test_captcha.py
# Should solve captcha and print: CAPTCHA solved successfully, token: <token>
```

---

### Task 5: Basic Playwright Scraper

**Goal:** Create a basic scraper that navigates to NC Courts Portal and performs a search.

**Steps:**

1. Create `scraper/page_parser.py` with:
   - `parse_search_results(page)` - extracts case numbers and URLs from results
   - `parse_case_detail(page)` - extracts case info, events from case page
   - `is_foreclosure_case(case_data)` - checks if case is foreclosure
   - Helper functions for extracting data from HTML

2. Create `scraper/initial_scrape.py` with:
   - Command-line argument parsing (county, start_date, end_date)
   - VPN verification at start
   - Playwright browser launch (headless=False for development)
   - Navigate to portal
   - Fill search form (county, case type, dates, search text)
   - Call CapSolver for reCAPTCHA
   - Submit search
   - Check for "too many results" error
   - Extract total case count
   - Handle pagination
   - For each case: click through, check if foreclosure, extract data
   - Save to database
   - Logging at each step

3. Create minimal test mode:
   - `--test` flag limits to first 5 cases
   - Useful for validation without long scrapes

**Files created:**
- `scraper/page_parser.py`
- `scraper/initial_scrape.py`

**Verification:**
```bash
# Test with Wake County, January 2024, first 5 cases
python scraper/initial_scrape.py --county wake --start 2024-01-01 --end 2024-01-31 --test

# Should:
# - Verify VPN
# - Navigate to portal
# - Fill form
# - Solve captcha
# - Get results
# - Process 5 cases
# - Save foreclosures to database
# - Print summary
```

Query database to verify:
```sql
psql -U nc_user -d nc_foreclosures -c "SELECT case_number, county_name, file_date FROM cases;"
```

---

### Task 6: Integration Testing

**Goal:** Verify all components work together end-to-end.

**Steps:**

1. Create `tests/test_phase1_integration.py`:
   - Test VPN verification
   - Test database connection
   - Test CapSolver integration
   - Test scraper on 1 known foreclosure case

2. Run full integration test:
```bash
# Wake County, Feb 2024, limited to 10 cases
python scraper/initial_scrape.py --county wake --start 2024-02-01 --end 2024-02-28 --limit 10
```

3. Verify in database:
   - Cases table populated
   - Case events table has events
   - Scrape logs show success
   - No errors in logs

4. Document any issues found and fixes applied

**Files created:**
- `tests/test_phase1_integration.py`
- `tests/__init__.py`

**Verification:**
- All tests pass
- Database has real foreclosure data
- Scraper handles pagination correctly
- Error handling works (test with VPN off, bad API key, etc.)

---

### Task 7: Documentation

**Goal:** Document Phase 1 setup and usage.

**Steps:**

1. Update `CLAUDE.md` with Phase 1 information:
   - How to set up PostgreSQL
   - How to configure .env
   - How to run initial scrape
   - Database schema overview

2. Create `docs/SETUP.md`:
   - Step-by-step setup instructions
   - Troubleshooting common issues
   - How to verify installation

3. Create `README.md` in project root:
   - Project overview
   - Quick start guide
   - Link to detailed docs

**Files created/updated:**
- `CLAUDE.md` (updated)
- `docs/SETUP.md`
- `README.md`

**Verification:**
- Documentation is clear and complete
- Fresh install following docs succeeds

---

## Definition of Done

Phase 1 is complete when:

- [ ] PostgreSQL database running with all tables created
- [ ] VPN verification working (blocks scraping if VPN off)
- [ ] CapSolver successfully solving reCAPTCHA
- [ ] Scraper can search NC Courts Portal
- [ ] Scraper extracts case numbers and URLs from results
- [ ] Scraper navigates to case details
- [ ] Scraper identifies foreclosure cases correctly
- [ ] Foreclosure data saved to database (cases + events)
- [ ] Scrape logs track all scraping activity
- [ ] Can scrape Wake County, 1 month, with 100% accuracy
- [ ] All integration tests pass
- [ ] Documentation complete and verified

## Non-Goals for Phase 1

- PDF downloading (Phase 2)
- OCR processing (Phase 2)
- Daily scraper (Phase 2)
- AI analysis (Phase 3)
- Web application (Phase 4)
- Scheduling automation (Phase 5)

## Test Case for Acceptance

Run this command and verify results:

```bash
python scraper/initial_scrape.py \
  --county wake \
  --start 2024-03-01 \
  --end 2024-03-31 \
  --limit 20
```

Expected results:
- VPN verified
- Search executes successfully
- ~20 cases processed (some may not be foreclosures)
- Foreclosure cases saved to database
- Database query shows cases with events
- Scrape log shows success
- No unhandled errors

## Estimated Completion

7 tasks, each approximately 1-2 hours of focused work = 1-2 days of development time.

## Next Steps After Phase 1

Once Phase 1 is complete:
1. Merge feature branch to main
2. Brainstorm Phase 2 details (PDF download, OCR, daily scraper)
3. Create Phase 2 implementation plan
4. Begin Phase 2 development
