# NC Foreclosures Project - Setup Guide

## Prerequisites

- Ubuntu/WSL environment
- Python 3.12+
- sudo access
- FROOT VPN account
- CapSolver API key

## Installation Steps

### 1. Clone Repository

```bash
cd ~/projects
git clone https://github.com/nash1515/nc_foreclosures.git
cd nc_foreclosures
```

### 2. Install PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo service postgresql start
```

### 3. Create Database

```bash
sudo -u postgres psql
```

In the PostgreSQL prompt:
```sql
CREATE DATABASE nc_foreclosures;
CREATE USER nc_user WITH PASSWORD 'nc_password';
GRANT ALL PRIVILEGES ON DATABASE nc_foreclosures TO nc_user;
GRANT ALL ON SCHEMA public TO nc_user;
\q
```

### 4. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 5. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Get your baseline IP (with VPN OFF)
curl ifconfig.me

# Edit .env and update:
nano .env
```

Update `.env` with:
- `VPN_BASELINE_IP` - Your IP address from above (with VPN OFF)
- `CAPSOLVER_API_KEY` - Your CapSolver API key
- `DATABASE_URL` - PostgreSQL connection string (default should work)

### 6. Initialize Database

```bash
# Set PYTHONPATH and run init script
PYTHONPATH=$(pwd) venv/bin/python database/init_db.py
```

You should see:
```
✓ Database initialized successfully!
```

### 7. Run Integration Tests

```bash
PYTHONPATH=$(pwd) venv/bin/python tests/test_phase1_integration.py
```

All 4 tests should pass.

## Verification

### Test Database Connection

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\dt"
```

Should show 5 tables: cases, case_events, documents, scrape_logs, user_notes

### Test VPN Manager

```bash
# With VPN OFF (should fail)
PYTHONPATH=$(pwd) venv/bin/python -c "from scraper.vpn_manager import verify_vpn_or_exit; verify_vpn_or_exit()"

# Should exit with error about VPN not connected

# With VPN ON (should pass)
# Turn on FROOT VPN, then run same command
```

### Test CapSolver

```bash
PYTHONPATH=$(pwd) venv/bin/python scraper/captcha_solver.py
```

Should show: ✓ CapSolver initialized successfully

## Running the Scraper

The scraper supports three modes for different use cases:

### Single Date Range (Direct Scraping)
```bash
# Scrape a specific date range across all counties
PYTHONPATH=$(pwd) venv/bin/python scraper/date_range_scrape.py \
  --start 2024-01-01 \
  --end 2024-01-31

# Skip existing cases (default behavior)
PYTHONPATH=$(pwd) venv/bin/python scraper/date_range_scrape.py \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --skip-existing

# Re-process existing cases
PYTHONPATH=$(pwd) venv/bin/python scraper/date_range_scrape.py \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --refresh-existing
```

### Batch Sequential Scraping
```bash
# Break large date ranges into chunks, process sequentially
PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --chunk monthly

# Chunk options: daily, weekly, monthly, quarterly, yearly
PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --chunk quarterly

# Search each county separately (avoids portal result limits)
PYTHONPATH=$(pwd) venv/bin/python scraper/batch_scrape.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --chunk monthly \
  --per-county
```

### Batch Parallel Scraping
```bash
# Process chunks in parallel for faster scraping
PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --chunk monthly \
  --workers 3

# Historical backfill example (per-county to avoid limits)
PYTHONPATH=$(pwd) venv/bin/python scraper/parallel_scrape.py \
  --start 2020-01-01 \
  --end 2025-11-24 \
  --chunk monthly \
  --per-county \
  --workers 3
```

### Scraper Architecture

All scrapers use `DateRangeScraper` as the core engine:

- **date_range_scrape.py** - Single search across all counties (1 CAPTCHA)
- **batch_scrape.py** - Sequential batch processing with configurable chunking
- **parallel_scrape.py** - Parallel batch processing with worker pools

**Key Features:**
- Default `--skip-existing` behavior prevents duplicate processing
- `--per-county` flag searches one county at a time (avoids portal limits)
- Date chunking utility supports daily/weekly/monthly/quarterly/yearly
- Automatic skipped case logging for transparency

## Troubleshooting

### PostgreSQL Service Not Running

```bash
sudo service postgresql start
sudo service postgresql status
```

### Permission Denied for Schema Public

```bash
sudo -u postgres psql -d nc_foreclosures -c "GRANT ALL ON SCHEMA public TO nc_user;"
```

### Module Not Found Errors

Make sure to set PYTHONPATH:
```bash
export PYTHONPATH=/home/ahn/projects/nc_foreclosures/.worktrees/phase1-foundation
# Or use it inline with commands
```

### VPN Verification Fails Even With VPN On

Update your baseline IP in `.env`:
```bash
# Get current IP with VPN OFF
curl ifconfig.me
# Update VPN_BASELINE_IP in .env with that value
```

## Next Steps

1. **Explore NC Courts Portal** - Use Playwright to interactively explore the portal and identify HTML selectors
2. **Implement Portal Parsing** - Fill in the TODO sections in `page_parser.py` and the scraper modules
3. **Test with Small Sample** - Run scraper on a small date range (1-2 months)
4. **Expand to Full Scraping** - Once verified, run larger scrapes with batch or parallel modes

## Project Structure

```
nc_foreclosures/
├── common/          # Shared utilities
├── database/        # Database models and connection
├── scraper/         # Web scraping modules
├── ocr/            # PDF processing (Phase 2)
├── analysis/       # AI analysis (Phase 3)
├── web_app/        # Flask web app (Phase 4)
├── tests/          # Integration tests
├── data/pdfs/      # Downloaded PDFs
└── docs/           # Documentation
```

## Development Workflow

1. Always activate virtual environment: `source venv/bin/activate`
2. Set PYTHONPATH for imports: `export PYTHONPATH=$(pwd)`
3. Commit frequently to git
4. Run tests after changes
5. Use `--test --limit N` flags when testing scraper
