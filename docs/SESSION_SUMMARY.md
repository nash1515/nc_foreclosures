# Session Summary - Dec 5, 2025 (Session 19)

## Current Project Status

### Database Statistics
- **Total Cases:** 1,731
- **Classifications:**
  - upcoming: 1,345 (active foreclosures, no sale yet)
  - closed_sold: 226 (sale completed, past upset period)
  - blocked: 70 (bankruptcy/stay in effect)
  - closed_dismissed: 56 (case dismissed/terminated)
  - upset_bid: 21 (within 10-day upset period - opportunities!)
  - unclassified: 13

### Infrastructure Status
- **PostgreSQL:** Running, 7 tables + extraction fields
- **Frontend:** React 19 + Vite + Ant Design on port 5173
- **Backend:** Flask + Flask-Dance on port 5000
- **Google OAuth:** Working (credentials in .env)
- **Scheduler:** 5 AM Mon-Fri automated scraping
- **Scraper:** All modules working (CAPTCHA, monitoring, PDF download)

## Session 19 Accomplishments (Dec 5, 2025)

### 1. OAuth Credentials Restored
- **Problem:** Google OAuth returning "invalid_client" error
- **Cause:** Credentials were lost from `.env` file between sessions
- **Solution:** Retrieved credentials from Claude conversation history
- **Added to .env:**
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `FLASK_SECRET_KEY`

### 2. Documentation Updated
- Updated CLAUDE.md with Session 19 notes
- Updated database statistics to current counts
- Updated environment variables documentation
- Refreshed TODO/Next Steps list

## Running the Application

### Start Everything
```bash
# Terminal 1: Start PostgreSQL
sudo service postgresql start

# Terminal 2: Start Flask backend
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python web_app/app.py

# Terminal 3: Start React frontend
cd /home/ahn/projects/nc_foreclosures/frontend
npm run dev
```

### Access Points
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:5000/api
- **OAuth Login:** Click "Sign in with Google" on frontend

## Development Workflow

### Feature Development with Git Worktrees
```bash
# Create isolated worktree
./scripts/dev_worktree.sh create my-feature

# Work in worktree
cd .worktrees/my-feature/frontend
npm install
npm run dev -- --port 5174

# When done
git add . && git commit -m "Feature complete"
git push origin feature/my-feature

# Merge and cleanup
cd /home/ahn/projects/nc_foreclosures
git checkout main
git merge feature/my-feature
./scripts/dev_worktree.sh delete my-feature
```

## Key Commands Reference

### Database
```bash
# Connect to database
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost

# Check classification counts
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c \
  "SELECT classification, COUNT(*) FROM cases GROUP BY classification ORDER BY COUNT(*) DESC;"
```

### Scraping
```bash
# Run daily scrape manually
./scripts/run_daily.sh

# Monitor specific cases
PYTHONPATH=$(pwd) venv/bin/python scraper/case_monitor.py --classification upset_bid

# Scheduler control
./scripts/scheduler_control.sh status
./scripts/scheduler_control.sh logs
```

### Scheduler API
```bash
# View schedule
curl http://localhost:5000/api/scheduler/config/daily_scrape

# Trigger manual run
curl -X POST http://localhost:5000/api/scheduler/run/daily_scrape
```

## Next Steps

1. **Frontend Enhancement** - Build Dashboard with real case data, charts, and filters
2. **Enrichment Module** - Add Zillow property data, county tax records
3. **Bidding Strategy Analysis** - Analyze 226 closed_sold cases for patterns

## Previous Sessions Quick Reference

| Session | Date | Focus |
|---------|------|-------|
| 19 | Dec 5 | OAuth fix, documentation update |
| 18 | Dec 4 | Multi-document popup fix, worktree workflow |
| 17 | Dec 4 | Report of Sale extraction, bid data validation |
| 16 | Dec 3 | Frontend Phase 1, PDF bid extraction |
| 15 | Dec 3 | Scheduler service, systemd integration |
| 14 | Dec 3 | Partition sales support |
| 13 | Dec 2 | Bot detection fix (user-agent) |
| 12 | Dec 2 | Retry logic, NULL events re-scrape |
| 11 | Dec 1 | Daily scraping system |
| 10 | Dec 1 | VPN removal |
| 9 | Nov 30-Dec 1 | AI analysis, classification cleanup |
| 8 | Nov 27 | Chatham County resolution |
| 7 | Nov 27 | Retry session |
| 6 | Nov 25 | Parallel batch scraper |
| 5 | Nov 25 | Extraction module |
| 4 | Nov 25 | PDF download, OCR |
| 3 | Nov 25 | Comprehensive data extraction |
| 2 | Nov 25 | Playwright MCP debugging |
| 1 | Nov 24 | Initial setup, VPN, CapSolver |

## Environment Variables Required (.env)

```bash
DATABASE_URL=postgresql://nc_user:nc_password@localhost/nc_foreclosures
CAPSOLVER_API_KEY=your-capsolver-key
ANTHROPIC_API_KEY=your-anthropic-key
PDF_STORAGE_PATH=./data/pdfs
LOG_LEVEL=INFO
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
FLASK_SECRET_KEY=your-flask-secret-key
```
