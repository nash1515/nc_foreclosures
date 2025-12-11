# Document Rescraping Checklist

Use this checklist when running document rescrapes.

---

## Pre-Flight Checklist

- [ ] **Environment activated**
  ```bash
  source venv/bin/activate
  export PYTHONPATH=/home/ahn/projects/nc_foreclosures
  ```

- [ ] **VPN connected**
  ```bash
  ./scripts/vpn_status.sh
  # Should show: VPN connected (IP: XXX.XXX.XXX.XXX)
  ```

- [ ] **PostgreSQL running**
  ```bash
  sudo service postgresql status
  # Should show: Active: active (running)
  ```

- [ ] **Baseline statistics captured**
  ```bash
  python scripts/check_document_stats.py > logs/stats_before_$(date +%Y%m%d).txt
  ```

---

## Option A: Fix Single Case (e.g., 25SP001706-910)

### Step 1: Analyze the Case

- [ ] **Check current state**
  ```bash
  PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost \
    -c "SELECT COUNT(*), document_name FROM documents WHERE case_id = (SELECT id FROM cases WHERE case_number = '25SP001706-910') GROUP BY document_name;"
  ```

- [ ] **Review document names for duplicates**
  - Note: Look for same filename appearing multiple times

### Step 2: Dry Run

- [ ] **Preview what will be done**
  ```bash
  python scripts/rescrape_case.py 25SP001706-910 --dry-run
  ```

- [ ] **Verify output makes sense**
  - Check: Number of documents to be deleted
  - Check: Case ID, county, classification shown correctly

### Step 3: Execute

- [ ] **Run the rescrape**
  ```bash
  python scripts/rescrape_case.py 25SP001706-910
  ```

- [ ] **Monitor output for errors**
  - Watch for: Download failures
  - Watch for: Browser crashes
  - Watch for: VPN disconnections

### Step 4: Verify

- [ ] **Check documents were downloaded**
  ```bash
  PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost \
    -c "SELECT document_name, document_date FROM documents WHERE case_id = (SELECT id FROM cases WHERE case_number = '25SP001706-910') ORDER BY document_date;"
  ```

- [ ] **Verify no more duplicates**
  ```bash
  python scripts/check_document_stats.py --show-duplicates | grep 25SP001706-910
  # Should show nothing if duplicates are fixed
  ```

- [ ] **Check PDF files on disk**
  ```bash
  ls -lh data/pdfs/wake/25SP001706-910/
  ```

---

## Option B: Bulk Rescrape All Upcoming Cases

### Step 1: Pre-Flight Checks

- [ ] **Check current statistics**
  ```bash
  python scripts/check_document_stats.py --classification upcoming --show-missing
  ```

- [ ] **Note baseline numbers**
  - Total upcoming cases: ___________
  - Cases with documents: ___________
  - Cases without documents: ___________

- [ ] **Ensure adequate disk space**
  ```bash
  df -h /home/ahn/projects/nc_foreclosures/data/pdfs
  # Should have at least 10GB free
  ```

### Step 2: Test Run

- [ ] **Test with small sample**
  ```bash
  python scripts/rescrape_upcoming.py --limit 5 --dry-run
  ```

- [ ] **Review sample output**
  - Check: Correct case count shown
  - Check: Statistics look reasonable

- [ ] **Test actual execution with 3 cases**
  ```bash
  python scripts/rescrape_upcoming.py --limit 3
  ```

- [ ] **Verify test run succeeded**
  - Check: No errors in output
  - Check: Documents downloaded
  - Check: VPN stayed connected

### Step 3: Full Rescrape

- [ ] **Create logs directory**
  ```bash
  mkdir -p logs
  ```

- [ ] **Start background job**
  ```bash
  nohup python scripts/rescrape_upcoming.py > logs/rescrape_$(date +%Y%m%d_%H%M%S).log 2>&1 &
  ```

- [ ] **Note PID for monitoring**
  ```bash
  echo $! > logs/rescrape.pid
  ```

### Step 4: Monitor Progress

- [ ] **Check process is running**
  ```bash
  ps aux | grep rescrape_upcoming
  ```

- [ ] **Monitor log output**
  ```bash
  tail -f logs/rescrape_*.log
  ```

- [ ] **Check for errors periodically**
  ```bash
  grep -i error logs/rescrape_*.log | tail -20
  ```

- [ ] **Monitor VPN connection**
  ```bash
  # Every hour, check VPN is still connected
  ./scripts/vpn_status.sh
  ```

### Step 5: Post-Run Verification

- [ ] **Check job completed**
  ```bash
  tail -100 logs/rescrape_*.log
  # Look for "RESCRAPE COMPLETE"
  ```

- [ ] **Compare statistics**
  ```bash
  python scripts/check_document_stats.py --classification upcoming
  ```

- [ ] **Verify improvement**
  - Cases without documents should be lower
  - Total documents should be higher

- [ ] **Check for errors**
  ```bash
  grep -i "error\|failed" logs/rescrape_*.log | wc -l
  ```

- [ ] **Review any failed cases**
  ```bash
  grep -B2 "Failed to fetch" logs/rescrape_*.log
  ```

---

## Troubleshooting Checklist

### VPN Issues

- [ ] **VPN dropped during run**
  ```bash
  ./scripts/vpn_start.sh
  # Restart the rescrape job
  ```

- [ ] **VPN won't connect**
  ```bash
  # Try different server
  ./scripts/vpn_start.sh random-east
  ```

### Browser Issues

- [ ] **Browser crashes**
  ```bash
  # Reduce parallel workers
  python scripts/rescrape_upcoming.py --workers 4
  ```

- [ ] **Playwright errors**
  ```bash
  # Install/reinstall browsers
  playwright install chromium
  ```

### Database Issues

- [ ] **Connection errors**
  ```bash
  # Check PostgreSQL is running
  sudo service postgresql status
  sudo service postgresql start
  ```

- [ ] **Permission errors**
  ```bash
  # Verify connection string
  grep DATABASE_URL .env
  ```

### Performance Issues

- [ ] **Too slow**
  ```bash
  # Increase workers (if system can handle it)
  python scripts/rescrape_upcoming.py --workers 12
  ```

- [ ] **Out of memory**
  ```bash
  # Decrease workers
  python scripts/rescrape_upcoming.py --workers 4
  ```

---

## Post-Completion Tasks

- [ ] **Generate final statistics report**
  ```bash
  python scripts/check_document_stats.py --show-duplicates --show-missing > logs/stats_after_$(date +%Y%m%d).txt
  ```

- [ ] **Compare before/after**
  ```bash
  diff logs/stats_before_*.txt logs/stats_after_*.txt
  ```

- [ ] **Document any issues encountered**
  - Create GitHub issue if scraper bugs found
  - Update documentation if needed

- [ ] **Clean up old log files**
  ```bash
  # Archive logs older than 30 days
  find logs/ -name "*.log" -mtime +30 -exec gzip {} \;
  ```

---

## Success Criteria

### Single Case Rescrape
- ✅ Duplicate documents removed
- ✅ Correct number of unique documents downloaded
- ✅ All expected document types present (Notice of Hearing, etc.)
- ✅ No errors in output

### Bulk Rescrape
- ✅ Cases without documents reduced significantly (target: < 5%)
- ✅ No increase in duplicate documents
- ✅ Error rate < 5% of total cases
- ✅ All upset_bid cases have complete document sets

---

## Record Keeping

**Date**: ___________________

**Type**: [ ] Single Case  [ ] Bulk Rescrape

**Cases Processed**: ___________________

**Documents Downloaded**: ___________________

**Errors Encountered**: ___________________

**Time Taken**: ___________________

**Notes**:
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________
_____________________________________________________________________________

**Verified By**: ___________________

---

## Next Steps After Rescrape

- [ ] **Investigate why documents were missing**
  - Check daily scraper configuration
  - Review `download_all_case_documents()` logic
  - Test with newly filed cases

- [ ] **Fix duplicate document issues**
  - Investigate Chatham county cases (100+ duplicates)
  - Review popup handler in `pdf_downloader.py`
  - Improve filename generation

- [ ] **Update daily scraper**
  - Ensure new cases get documents downloaded
  - Add better error handling
  - Add document count validation

- [ ] **Schedule regular rescrapes**
  - Weekly rescrape of upcoming cases?
  - Monthly full rescrape?
  - Add to scheduler configuration

---

## Quick Reference

```bash
# Setup
source venv/bin/activate && export PYTHONPATH=$(pwd)

# Check stats
python scripts/check_document_stats.py --show-missing

# Fix one case
python scripts/rescrape_case.py 25SP001706-910 --dry-run
python scripts/rescrape_case.py 25SP001706-910

# Rescrape all upcoming
nohup python scripts/rescrape_upcoming.py > logs/rescrape_$(date +%Y%m%d).log 2>&1 &
tail -f logs/rescrape_*.log
```

---

**For detailed documentation, see**: `scripts/RESCRAPE_README.md`
