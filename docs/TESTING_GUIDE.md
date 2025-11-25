# NC Foreclosures Scraper - Testing Guide

## Phase 1 Implementation: COMPLETE ✅

All core components have been implemented:

### ✅ Completed Components
1. **Database Schema & Models** - PostgreSQL with SQLAlchemy ORM
2. **VPN Manager** - IP verification to ensure VPN is active
3. **CapSolver Integration** - reCAPTCHA solving
4. **Portal Selectors** - All HTML selectors identified
5. **Portal Interactions** - Form filling, CAPTCHA solving, navigation
6. **HTML Parsing** - Search results and case detail parsing
7. **Initial Scraper** - Complete scraping workflow

### 📋 Implementation Details

**Files Updated:**
- `scraper/initial_scrape.py` - Integrated portal interactions
- `scraper/page_parser.py` - Implemented HTML parsing functions

**Portal Integration:**
- Form filling with county, date range, and search criteria
- reCAPTCHA solving with CapSolver API
- Error detection for "too many results"
- Pagination through result pages
- Case detail extraction

**HTML Parsing:**
- Search results table parsing
- Case information extraction
- Event timeline parsing
- Document list parsing (for Phase 2)

## Testing Instructions

### Prerequisites

Before testing, ensure:

1. **VPN is active** (FROOT VPN or similar)
2. **PostgreSQL is running**
3. **CapSolver has credits** (check balance at capsolver.com)
4. **Environment variables set** (`.env` file configured)

### Quick Test Command

```bash
# Activate environment
cd /home/ahn/projects/nc_foreclosures/.worktrees/phase1-foundation
source venv/bin/activate
export PYTHONPATH=$(pwd)

# Test with 5 cases from Wake County in January 2024
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --test \
  --limit 5
```

### What to Watch For

The scraper will:

1. ✅ Verify VPN connection
2. ✅ Create scrape log in database
3. ✅ Launch browser (non-headless for visibility)
4. ✅ Navigate to NC Courts Portal
5. ✅ Click "Advanced" filter
6. ✅ Fill search form with county, dates, and search pattern
7. ✅ Solve reCAPTCHA
8. ✅ Submit search
9. ✅ Extract total count from results
10. ✅ Parse each result row
11. ✅ Visit each case detail page
12. ✅ Check if case is foreclosure
13. ✅ Save foreclosure cases to database
14. ✅ Navigate to next page (if more results)
15. ✅ Update scrape log with completion status

### Expected Behavior

**Console Output:**
```
============================================================
STARTING INITIAL SCRAPE
============================================================
INFO - VPN verified: 136.61.20.173
INFO - Created scrape log (ID: 1)
INFO - Navigating to https://portal-nc.tylertech.cloud/...
INFO - Filling search form...
INFO - Solving CAPTCHA...
INFO - Submitting search...
INFO - Found 42 total cases
INFO - Processing page 1...
INFO - Processing case: 24SP000123
INFO -   ✓ Foreclosure case identified
INFO -   Saved to database (ID: 1)
...
✓ Scrape completed successfully: 5 cases processed
```

**Browser Window:**
- You should see the browser open and navigate through the portal
- Forms will auto-fill
- CAPTCHA will solve automatically
- Pages will navigate as the scraper processes results

### Checking Results

```bash
# View scraped cases
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c \
  "SELECT case_number, county_name, case_type, case_status FROM cases;"

# View case events
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c \
  "SELECT c.case_number, e.event_date, e.event_type
   FROM cases c
   JOIN case_events e ON c.id = e.case_id
   ORDER BY c.case_number, e.event_date;"

# View scrape logs
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c \
  "SELECT * FROM scrape_logs ORDER BY started_at DESC LIMIT 5;"
```

## Common Issues & Solutions

### 1. VPN Not Detected
**Error:** `VPN VERIFICATION FAILED!`

**Solution:**
- Ensure VPN is active
- Update `VPN_BASELINE_IP` in `.env` with your actual non-VPN IP
- Test: `curl ifconfig.me`

### 2. CAPTCHA Fails
**Error:** `Failed to solve CAPTCHA`

**Solution:**
- Check CapSolver balance: https://dashboard.capsolver.com/
- Verify `CAPSOLVER_API_KEY` in `.env`
- CapSolver may be slow (30-60 seconds is normal)

### 3. Selectors Don't Match
**Error:** Element not found or no results parsed

**Solution:**
- Portal HTML structure may have changed
- Check `portal_analysis/` directory for captured HTML
- Update selectors in `scraper/portal_selectors.py`
- Use browser DevTools to inspect actual elements

### 4. Too Many Results
**Error:** `Too many results - implement date range splitting`

**Solution:**
- Reduce date range (e.g., 1 month instead of 1 year)
- Portal limits results to ~500 cases per query
- Future enhancement: auto-split date ranges

### 5. Database Connection Failed
**Error:** `could not connect to server`

**Solution:**
```bash
# Start PostgreSQL
sudo service postgresql start

# Test connection
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT 1"
```

## Next Steps After Successful Test

1. **Test with larger sample** - Increase `--limit` to 50-100 cases
2. **Test multiple counties** - Run for Durham, Orange, etc.
3. **Test longer date ranges** - Full month, quarter, or year
4. **Review data quality** - Check if foreclosure detection works correctly
5. **Optimize performance** - Adjust wait times, add parallel processing

## Phase 2 Preparation

Once Phase 1 testing is complete:

1. **Merge to main** - Create PR for `feature/phase1-foundation`
2. **Begin Phase 2** - PDF downloading and OCR
3. **Add document download** - Use `case_data['documents']`
4. **Implement OCR** - Tesseract or cloud OCR service
5. **Extract structured data** - Parse sale dates, amounts, parties

## Resources

- **Portal URL:** https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29
- **CapSolver Dashboard:** https://dashboard.capsolver.com/
- **GitHub Repo:** https://github.com/nash1515/nc_foreclosures
- **Project Docs:** `docs/` directory
