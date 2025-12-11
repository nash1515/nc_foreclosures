# Download Missing Documents Guide

## Overview

The `download_missing_documents.py` script downloads PDF documents for all cases that currently have 0 documents in the database.

**Current Status:** 303 cases with 0 documents
- Wake: 220 cases
- Durham: 48 cases
- Harnett: 12 cases
- Orange: 14 cases
- Lee: 8 cases
- Chatham: 1 case

## Why Cases Have 0 Documents

1. **Early scrapes** didn't download documents properly (pre-pdf_downloader implementation)
2. **date_range_scrape** only downloads docs on first case creation, not on updates
3. Some cases may genuinely have no documents attached yet

## Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Run the script
PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python scripts/download_missing_documents.py
```

## What the Script Does

1. **Queries database** for all cases with 0 documents
2. **Shows summary** by county and asks for confirmation
3. **Launches browser** (headless=False for Angular compatibility)
4. **For each case:**
   - Navigates to case_url
   - Waits for page to load and Angular to render
   - Clicks document buttons and downloads PDFs
   - Creates Document records in database
   - Organized by county/case_number in `data/pdfs/`
5. **Reports results** with detailed statistics

## Expected Runtime

- **~303 cases** to process
- **~1-3 seconds** per case (navigation + download + delays)
- **Total: ~15-20 minutes** for all cases

## What Gets Downloaded

The script uses `download_case_documents()` which downloads:
- ALL documents attached to the case
- Organized by event type and date
- Saved to `data/pdfs/{county}/{case_number}/`
- Database records created with event associations

## Error Handling

The script handles:
- Missing URLs (skips case)
- Navigation timeouts (logs error, continues)
- Missing documents (reports as "no documents found")
- Download failures (logs error, continues)

## Output

```
Found 303 cases with 0 documents

Cases by county:
  Chatham: 1
  Durham: 48
  Harnett: 12
  Lee: 8
  Orange: 14
  Wake: 220

Download documents for all 303 cases? (y/n): y

[1/303] Processing 23SP000185-180 (Chatham)...
  ✓ Downloaded 3 document(s)

[2/303] Processing 20SP000049-310 (Durham)...
  ℹ️  No documents found on case page

...

===========================================================
SUMMARY
===========================================================
Total cases processed:        303
Cases with downloads:         250
Cases with no documents:      40
Cases with no URL:            0
Cases that failed:            13

Cases still with 0 documents: 53
```

## After Running

Check how many cases still have 0 documents:

```bash
PYTHONPATH=/home/ahn/projects/nc_foreclosures venv/bin/python -c "
from database.connection import get_session
from sqlalchemy import text

with get_session() as session:
    result = session.execute(text('''
        SELECT COUNT(*) as cnt
        FROM (
            SELECT c.id
            FROM cases c
            LEFT JOIN documents d ON c.id = d.case_id
            GROUP BY c.id
            HAVING COUNT(d.id) = 0
        ) subq
    ''')).fetchone()
    print(f'Cases with 0 documents: {result[0]}')
"
```

## Troubleshooting

### Script hangs on a case
- Browser may be waiting for user input (CAPTCHA?)
- Press Ctrl+C to stop, script will resume next time from where it left off

### "No documents found" for many cases
- Some cases genuinely have no documents yet
- Check a few manually on the NC Courts portal

### Downloads fail
- Check disk space in `data/pdfs/`
- Check network connectivity
- Check database connection

## Re-running the Script

Safe to re-run! The script:
- Only queries cases with 0 documents
- Won't re-download existing documents
- `download_case_documents()` handles duplicates

## Related Scripts

- **ocr_report_of_sale_docs.py** - Extract bid amounts from Report of Sale PDFs
- **fix_missing_bid_amounts_v2.py** - Fill in missing bid amounts after downloading docs
