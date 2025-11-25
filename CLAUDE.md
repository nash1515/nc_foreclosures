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

**Phase 1 Foundation:** ✅ Complete
**Current Branch:** `feature/phase1-foundation` (in worktree `.worktrees/phase1-foundation/`)

### Completed Components
- PostgreSQL database with full schema (5 tables)
- SQLAlchemy ORM models
- VPN verification system
- CapSolver reCAPTCHA integration
- Playwright scraper framework
- Integration tests (all passing)

### Next Steps
- Explore NC Courts Portal HTML structure
- Implement portal-specific parsing in `scraper/page_parser.py`
- Test scraper with small samples
- Begin Phase 2: PDF downloading and OCR

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

### Running the Scraper

**Note:** Portal parsing not yet implemented. Framework is ready.

```bash
# Example command (once parsing implemented)
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --test \
  --limit 10
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
- `scraper/captcha_solver.py` - reCAPTCHA solving
- `scraper/page_parser.py` - HTML parsing (needs implementation)

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
- **VPN must be on:** Scraper will exit if VPN not detected
- **PostgreSQL must be running:** `sudo service postgresql start`
- **Portal parsing incomplete:** Placeholders in `page_parser.py` need actual HTML selectors

## Documentation

- `docs/SETUP.md` - Detailed setup instructions
- `docs/plans/2025-11-24-nc-foreclosures-architecture-design.md` - Full architecture
- `docs/plans/2025-11-24-phase1-foundation-implementation.md` - Phase 1 plan
- `PROJECT_REQUIREMENTS.md` - Original requirements
