# Document Rescraping Scripts

Two scripts for fixing document issues in the NC Foreclosures database.

## Quick Reference

```bash
# Setup (always run first)
source venv/bin/activate
export PYTHONPATH=/home/ahn/projects/nc_foreclosures

# Check VPN (required for NC Courts portal access)
./scripts/vpn_status.sh

# Start VPN if needed
./scripts/vpn_start.sh
```

---

## Script 1: `rescrape_case.py` - Single Case Rescrape

**Purpose**: Fix document issues for a specific case (e.g., duplicates, missing PDFs).

**What it does**:
1. Deletes all existing documents for the case from database
2. Optionally deletes PDF files from disk
3. Re-downloads ALL documents from NC Courts portal

**When to use**:
- Case has duplicate documents (like 25SP001706-910 with 28 identical Cover Sheets)
- Documents failed to download during initial scrape
- Need to refresh a single case's document set

### Usage

```bash
# Dry run - see what would be done
python scripts/rescrape_case.py 25SP001706-910 --dry-run

# Full rescrape - deletes DB records and files, re-downloads everything
python scripts/rescrape_case.py 25SP001706-910

# Keep PDF files on disk, just refresh DB records
python scripts/rescrape_case.py 25SP001706-910 --keep-files
```

### Options

- `case_number` - Required. Case number to rescrape (e.g., 25SP001706-910)
- `--keep-files` - Keep PDF files on disk (only delete database records)
- `--dry-run` - Preview what would be done without making changes

### Example Output

```
============================================================
RESCRAPING CASE: 25SP001706-910
============================================================
Case ID: 1598
County: Wake
Classification: upset_bid

Step 1: Deleting existing documents...
Deleted 28 document records from database
Deleted 1 files from disk

Step 2: Re-downloading documents from portal...
[case_monitor output...]

============================================================
RESCRAPE COMPLETE
============================================================
Database records deleted: 28
Files deleted from disk: 1
Events added: 0
Bid updates: 1
Documents after rescrape: 15
```

---

## Script 2: `rescrape_upcoming.py` - Bulk Rescrape

**Purpose**: Ensure all `upcoming` cases have complete document sets.

**What it does**:
1. Queries all cases with `classification='upcoming'`
2. For each case, downloads ANY missing documents
3. **SAFE**: Uses `skip_existing=True` - won't re-download files already in DB

**When to use**:
- Initial scrape didn't capture all documents
- Want to ensure document completeness across all upcoming cases
- After fixing scraper bugs, need to backfill missing docs

### Usage

```bash
# Dry run - see statistics and sample cases
python scripts/rescrape_upcoming.py --dry-run

# Test with first 10 cases
python scripts/rescrape_upcoming.py --limit 10

# Full rescrape - all 1360 upcoming cases
python scripts/rescrape_upcoming.py

# Run with more workers (faster but more resources)
python scripts/rescrape_upcoming.py --workers 12

# Run in background with logging (recommended for full run)
nohup python scripts/rescrape_upcoming.py > logs/rescrape_upcoming.log 2>&1 &

# Monitor progress
tail -f logs/rescrape_upcoming.log
```

### Options

- `--limit N` - Process only first N cases (for testing)
- `--workers N` - Number of parallel browser instances (default: 8)
- `--headless` - Run browsers in headless mode (default: visible for reliability)
- `--dry-run` - Preview what would be done without making changes

### Example Output

```
======================================================================
RESCRAPING UPCOMING CASES FOR COMPLETE DOCUMENT SETS
======================================================================
Started at: 2025-12-09 17:00:00

Case Statistics:
  Total upcoming cases: 1360
  Cases with documents: 1094
  Cases without documents: 266

Cases to process: 1360

Initializing CaseMonitor with 8 parallel workers...

[Progress output...]

======================================================================
RESCRAPE COMPLETE
======================================================================
Completed at: 2025-12-09 18:30:00

Results:
  Cases processed: 1360
  New events added: 87
  Classifications changed: 12
  Bid updates: 3
  Errors: 0

Final Statistics:
  Cases with documents: 1320 (+226)
  Cases without documents: 40 (-226)
```

---

## Performance Estimates

### Single Case (`rescrape_case.py`)
- **Time**: 5-15 seconds per case
- **VPN Required**: Yes
- **Headless**: No (use visible browser for reliability)

### Bulk Rescrape (`rescrape_upcoming.py`)
- **Time**: ~1-2 seconds per case average (parallelized)
- **Total Time** (1360 cases, 8 workers): ~3-5 hours
- **VPN Required**: Yes
- **Headless**: Optional (visible is more reliable but slower)

---

## VPN Requirements

Both scripts require VPN connection to access NC Courts portal.

```bash
# Check if VPN is connected
./scripts/vpn_status.sh

# Start VPN
./scripts/vpn_start.sh

# Start VPN with specific server
./scripts/vpn_start.sh virginia    # Default
./scripts/vpn_start.sh florida
./scripts/vpn_start.sh random-east
```

**Baseline IP**: `136.61.20.173` (your non-VPN IP)

---

## Safety Features

### `rescrape_case.py`
- ⚠️ **DESTRUCTIVE** - Deletes documents before re-downloading
- Use `--dry-run` first to preview
- Use `--keep-files` to preserve PDF files

### `rescrape_upcoming.py`
- ✅ **SAFE** - Never deletes anything
- Uses `skip_existing=True` in `download_all_case_documents()`
- Only downloads documents NOT already in database
- Idempotent - safe to run multiple times

---

## Common Use Cases

### Fix Case 25SP001706-910 (28 duplicate Cover Sheets)

```bash
# 1. Preview
python scripts/rescrape_case.py 25SP001706-910 --dry-run

# 2. Execute
python scripts/rescrape_case.py 25SP001706-910

# 3. Verify
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost \
  -c "SELECT document_name, document_date FROM documents WHERE case_id=1598;"
```

### Backfill Missing Documents for All Upcoming Cases

```bash
# 1. Check VPN
./scripts/vpn_status.sh || ./scripts/vpn_start.sh

# 2. Test with sample
python scripts/rescrape_upcoming.py --limit 5 --dry-run

# 3. Run in background
nohup python scripts/rescrape_upcoming.py > logs/rescrape_$(date +%Y%m%d).log 2>&1 &

# 4. Monitor progress
tail -f logs/rescrape_*.log

# 5. Check results
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost \
  -c "SELECT classification,
      COUNT(DISTINCT c.id) as cases,
      COUNT(d.id) as total_docs
      FROM cases c LEFT JOIN documents d ON c.id = d.case_id
      WHERE c.classification = 'upcoming'
      GROUP BY c.classification;"
```

### Test with a Few Cases Before Full Run

```bash
# Test with 10 cases, see detailed output
python scripts/rescrape_upcoming.py --limit 10

# Check for errors, if clean, run full
python scripts/rescrape_upcoming.py
```

---

## Architecture Notes

### How Documents Are Downloaded

Both scripts use `CaseMonitor` from `scraper/case_monitor.py`:

1. **Navigate to case URL** (no CAPTCHA needed - direct link)
2. **Parse events** from Angular app
3. **Call `download_all_case_documents()`** from `scraper/pdf_downloader.py`
4. **Extract document buttons** using JavaScript
5. **Click each button** to trigger download
6. **Handle multi-document popups** if present
7. **Save to disk** at `data/pdfs/{county}/{case_number}/`
8. **Create database records** in `documents` table

### Why `skip_existing=True` is Safe

The `download_all_case_documents()` function:
```python
def download_all_case_documents(page, case_id, county, case_number, skip_existing=True):
    # 1. Query existing documents from DB
    existing_docs = set()
    if skip_existing:
        docs = session.query(Document).filter_by(case_id=case_id).all()
        for doc in docs:
            existing_docs.add(doc.document_name)

    # 2. For each document on portal page:
    if skip_existing and expected_filename in existing_docs:
        # Skip download, just return metadata
        continue

    # 3. Otherwise, download the new document
```

This means:
- If a document with the same filename exists in DB → **Skip**
- If a document is missing from DB → **Download**
- **Never deletes** or overwrites existing records

---

## Troubleshooting

### "VPN not connected"
```bash
./scripts/vpn_start.sh
# Wait 15 seconds for connection
./scripts/vpn_status.sh
```

### "PYTHONPATH not set"
```bash
export PYTHONPATH=/home/ahn/projects/nc_foreclosures
```

### "Failed to fetch page after 4 attempts"
- VPN may have dropped - check with `./scripts/vpn_status.sh`
- Portal may be down - check manually in browser
- Try reducing `--workers` to avoid rate limiting

### "Browser crashes in headless mode"
- Don't use `--headless` - visible browser is more reliable
- Angular apps in NC Courts portal often fail in headless

### Monitor long-running jobs
```bash
# Check process is still running
ps aux | grep rescrape_upcoming

# Check log output
tail -f logs/rescrape_*.log

# Check database progress
watch -n 60 'PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT COUNT(*) FROM documents;"'
```

---

## Database Queries for Verification

```sql
-- Count documents per case
SELECT c.case_number, c.classification, COUNT(d.id) as doc_count
FROM cases c
LEFT JOIN documents d ON c.id = d.case_id
WHERE c.classification = 'upcoming'
GROUP BY c.id
ORDER BY doc_count DESC
LIMIT 20;

-- Find cases with no documents
SELECT case_number, county_name, file_date
FROM cases c
WHERE classification = 'upcoming'
  AND NOT EXISTS (SELECT 1 FROM documents WHERE case_id = c.id)
ORDER BY file_date DESC;

-- Check for duplicate document names in a case
SELECT case_id, document_name, COUNT(*) as dup_count
FROM documents
WHERE case_id = 1598
GROUP BY case_id, document_name
HAVING COUNT(*) > 1;
```

---

## Related Files

- `scraper/case_monitor.py` - Main logic for monitoring/rescaping cases
- `scraper/pdf_downloader.py` - Document download and handling
- `database/models.py` - Database schema (Document, Case tables)
- `common/config.py` - PDF storage paths
- `scripts/vpn_start.sh` - VPN connection script
- `scripts/vpn_status.sh` - VPN status check

---

## Future Enhancements

Potential improvements:
- [ ] Add `--county` filter to rescrape_upcoming.py
- [ ] Add progress bar for long runs
- [ ] Export rescrape results to CSV
- [ ] Add email notification on completion
- [ ] Integrate with scheduler for automated weekly rescrapes
