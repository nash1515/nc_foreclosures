# Catch-Up Scrape + Daily Scrape Foundation

## Current State
- Last scraped file date: **Nov 26, 2025**
- Today: **Dec 1, 2025**
- Gap to fill: **Nov 27 - Nov 30, 2025** (4 days)
- Database has upsert logic (won't duplicate existing cases)

## Problem
The existing `parallel_batch_scrape.py` CLI only accepts `--year` parameter, then internally splits into monthly (Wake) or quarterly (others) ranges to avoid hitting result limits. For short date ranges like catch-up or daily scrapes, we need direct `--start/--end` support.

## Plan

### Step 1: Add Date Range Support to Parallel Scraper

Modify `scraper/parallel_batch_scrape.py` to accept `--start` and `--end` date arguments:

```bash
# New usage:
python scraper/parallel_batch_scrape.py --start 2025-11-27 --end 2025-11-30
python scraper/parallel_batch_scrape.py --start 2025-11-27 --end 2025-11-30 --county wake
```

**Key insight:** For short date ranges (daily/catch-up), we won't hit result limits, so ALL 6 counties can use the same date range simultaneously - no need for monthly/quarterly splitting.

**Changes needed:**
1. Add `--start` and `--end` argparse arguments (make `--year` no longer required)
2. When `--start/--end` provided, use that exact range for all counties
3. Keep `--year` for backwards compatibility (uses existing monthly/quarterly logic)
4. Validate that either `--year` OR `--start/--end` is provided (not both, not neither)

### Step 2: Add VPN Server Rotation

Update `scripts/vpn_start.sh` to support random selection from East Coast/Midwest servers:

**Available servers (already configured):**
- Virginia (East Coast)
- Florida (East Coast)
- Georgia (East Coast)
- New York (East Coast)
- Illinois (Midwest)

Add a `random-east` option that picks randomly from these 5 servers.

### Step 3: Run Catch-Up Scrape

```bash
# 1. Start VPN (with server rotation)
./scripts/vpn_start.sh random-east

# 2. Run catch-up scrape for Nov 27-30 (all 6 counties, same date range)
PYTHONPATH=$(pwd) python3 scraper/parallel_batch_scrape.py \
  --start 2025-11-27 \
  --end 2025-11-30

# 3. Run OCR on new documents
PYTHONPATH=$(pwd) python3 ocr/run_ocr.py

# 4. Run extraction/classification
PYTHONPATH=$(pwd) python3 extraction/run_extraction.py
```

## Files to Modify

1. **`scraper/parallel_batch_scrape.py`**
   - Add `--start` and `--end` arguments
   - Make `--year` optional (no longer `required=True`)
   - Add validation: require either `--year` OR both `--start` and `--end`
   - When using date range mode, all counties get the same range (no splitting)

2. **`scripts/vpn_start.sh`**
   - Add `random-east` option for random East Coast/Midwest server selection

## Implementation Details

### parallel_batch_scrape.py Changes

```python
# In argparse section:
parser.add_argument('--year', type=int, help='Year to scrape (uses monthly/quarterly splits)')
parser.add_argument('--start', type=str, help='Start date YYYY-MM-DD (for date range mode)')
parser.add_argument('--end', type=str, help='End date YYYY-MM-DD (for date range mode)')

# In main(), add validation and logic:
if args.start and args.end:
    # Date range mode - same range for all counties
    start_date = datetime.strptime(args.start, '%Y-%m-%d').date()
    end_date = datetime.strptime(args.end, '%Y-%m-%d').date()
    # Run all counties with this single date range
    ...
elif args.year:
    # Year mode - existing monthly/quarterly logic
    ...
else:
    parser.error('Either --year or both --start and --end required')
```

### vpn_start.sh Changes

```bash
# Add to case statement:
random-east)
    SERVERS=("United States - Virginia.ovpn" "United States - Florida.ovpn" \
             "United States - Georgia.ovpn" "United States - New York.ovpn" \
             "United States - Illinois.ovpn")
    CONFIG="${SERVERS[$RANDOM % ${#SERVERS[@]}]}"
    echo "Randomly selected: $CONFIG"
    ;;
```

## Verification

1. Test with `--dry-run`: `python scraper/parallel_batch_scrape.py --start 2025-11-27 --end 2025-11-30 --dry-run`
2. Verify VPN rotation: `./scripts/vpn_start.sh random-east` (run a few times)
3. Run actual catch-up scrape
4. Verify new cases: `SELECT COUNT(*) FROM cases WHERE file_date >= '2025-11-27'`
