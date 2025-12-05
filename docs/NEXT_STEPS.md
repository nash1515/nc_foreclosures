# NC Foreclosures - Next Steps

## Current Status (Dec 5, 2025)

**All Core Infrastructure:** ✅ Complete
**Database:** 1,731 cases across 6 NC counties
**Frontend:** React + Vite + Ant Design (working)
**Backend:** Flask + Google OAuth (working)
**Scheduler:** 5 AM Mon-Fri automated scraping (working)

### Phase Completion Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Database, scraping, Kendo UI parsing |
| Phase 2 | ✅ Complete | PDF download, OCR processing |
| Phase 2.5 | ✅ Complete | Data extraction, classification |
| Phase 3 | ✅ Complete | AI analysis integration (Claude API) |
| Phase 4 | 🔄 In Progress | Frontend web application |

### Current Database Statistics

```
upcoming:         1,345 (active foreclosures)
closed_sold:        226 (completed sales)
blocked:             70 (bankruptcy/stay)
closed_dismissed:    56 (dismissed cases)
upset_bid:           21 (bidding opportunities!)
unclassified:        13
─────────────────────────
TOTAL:            1,731
```

## Immediate Next Steps

### 1. Frontend Enhancement (Priority: High)
The frontend shell is complete. Next steps:
- Connect Dashboard to real API data
- Display case statistics with charts
- Build case list with filtering/sorting
- Implement case detail view
- Add upset_bid opportunity highlights

### 2. Enrichment Module (Priority: Medium)
Add external data sources:
- Zillow property values and estimates
- County tax records
- Property ownership history
- Nearby comparable sales

### 3. Bidding Strategy Analysis (Priority: Medium)
Analyze 226 closed_sold cases:
- Winning bid patterns by county
- Time from sale to upset bid deadline
- Equity estimation accuracy
- Success rate predictions

## Running the Application

### Quick Start
```bash
# Terminal 1: PostgreSQL
sudo service postgresql start

# Terminal 2: Backend (port 5000)
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python web_app/app.py

# Terminal 3: Frontend (port 5173)
cd /home/ahn/projects/nc_foreclosures/frontend
npm run dev
```

### Access
- **Frontend:** http://localhost:5173
- **API:** http://localhost:5000/api
- **Login:** Google OAuth via "Sign in with Google"

## Key Commands

### Database
```bash
# Connect
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost

# View classifications
SELECT classification, COUNT(*) FROM cases
GROUP BY classification ORDER BY COUNT(*) DESC;

# View upset_bid opportunities
SELECT case_number, property_address, current_bid_amount, next_bid_deadline
FROM cases WHERE classification = 'upset_bid';
```

### Scraping
```bash
# Manual daily scrape
./scripts/run_daily.sh

# Monitor upset_bid cases specifically
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upset_bid

# Scheduler control
./scripts/scheduler_control.sh status
./scripts/scheduler_control.sh logs
```

### Development
```bash
# Create feature worktree
./scripts/dev_worktree.sh create my-feature

# Work in isolation
cd .worktrees/my-feature/frontend
npm install && npm run dev -- --port 5174

# Cleanup when done
./scripts/dev_worktree.sh delete my-feature
```

## Architecture Overview

```
nc_foreclosures/
├── common/          # Config, logging, county codes
├── database/        # SQLAlchemy models, connection
├── scraper/         # Playwright scrapers, CAPTCHA
├── scheduler/       # Automated job service
├── extraction/      # Regex data extraction, classification
├── ocr/             # PDF text extraction (Tesseract)
├── analysis/        # Claude AI integration
├── web_app/         # Flask API + OAuth
├── frontend/        # React + Vite + Ant Design
├── scripts/         # Helper scripts
└── docs/            # Documentation
```

## Documentation Index

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | Main project guide (read this first) |
| `docs/SESSION_SUMMARY.md` | Latest session notes |
| `docs/SETUP.md` | Initial setup instructions |
| `docs/TESTING_GUIDE.md` | Testing procedures |
| `docs/KENDO_GRID_FIXES.md` | Portal parsing details |

## Notes

- VPN is NOT required - portal doesn't rate limit
- Scheduler runs at 5 AM Mon-Fri automatically
- OAuth credentials stored in `.env` (gitignored)
- Use worktrees for feature development
