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

**Phase 1 Foundation:** 🔧 In Progress (95%)
**Current Branch:** `feature/phase1-foundation` (in worktree `.worktrees/phase1-foundation/`)

### Completed Components
- ✅ PostgreSQL database with full schema (5 tables)
- ✅ SQLAlchemy ORM models
- ✅ VPN verification system (OpenVPN + FrootVPN)
- ✅ CapSolver reCAPTCHA integration
- ✅ Playwright scraper framework with stealth mode
- ✅ Integration tests (all passing)
- ✅ Kendo UI Grid parsing implementation

### In Progress
- 🔧 Kendo dropdown interaction (county works via JS, status/type timeout)
- 🔧 End-to-end scraper testing

### Next Steps
1. Fix Kendo dropdown timeouts for status and case type
2. Verify CAPTCHA solving works reliably
3. Test full scraping flow with limit=5
4. Begin Phase 2: PDF downloading and OCR

### Recent Updates (Nov 25, 2025) - Session 2
- **Playwright MCP Debugging:** Used Playwright MCP to examine actual page structures
- **Case Detail Page:** Portal uses "Register of Actions" (ROA) Angular app, NOT simple HTML
  - URL format: `/app/RegisterOfActions/?id={HASH}&isAuthenticated=False&mode=portalembed`
  - Case Type is in `table.roa-caseinfo-info-rows` with "Case Type:" label
  - Foreclosure cases have: `Case Type: Foreclosure (Special Proceeding)`
- **Foreclosure Identification (per project requirements):**
  1. Case Type = "Foreclosure (Special Proceeding)"
  2. OR events contain: "Foreclosure Case Initiated", "Findings And Order Of Foreclosure", "Report Of Foreclosure Sale (Chapter 45)", "Notice Of Sale/Resale", "Upset Bid Filed"
- **Search Results:** Case links have `data-url` attribute (not `href`)
  - Example: `<a class="caseLink" href="#" data-url="/app/RegisterOfActions/?id=...">`
- **Current Issue:** Scraper shows `Case Type: None, Events: 0` - page_parser not extracting data
- **Files Updated:**
  - `scraper/page_parser.py`: Updated `parse_case_detail()` to use ROA table selectors and text search
  - `scraper/initial_scrape.py`: Added debug logging for HTML content and wait time for Angular

### Next Steps (Resume Here)
1. Debug why `parse_case_detail()` returns None for case_type
2. Check if Angular app content is fully loaded before parsing (may need longer wait or JS execution)
3. Run scraper with LOG_LEVEL=DEBUG to see HTML being parsed
4. Test with known foreclosure URL: `https://portal-nc.tylertech.cloud/app/RegisterOfActions/#/CB7F93D047F5D8136929FC3D31CAF0CE485042EDECF8A4DF58E0F3FE9409E463374427EF66070493593DE9F43AAAA82EA883C942ACCA5E53BB7E26777702B16DF9CE499EA2FBBE5917C89A03E96A8585/anon/portalembed`

### Previous Updates (Nov 24, 2025)
- **VPN Setup:** OpenVPN configured with FrootVPN (Virginia server)
- **Portal Discovery:** Portal uses Kendo UI Grid, not simple HTML tables
- **Kendo Grid Support:** Updated selectors for grid, pagination, and pager info
- See `docs/KENDO_GRID_FIXES.md` for detailed implementation notes

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

### VPN Setup

**REQUIRED:** VPN must be running before scraping.

```bash
# Start VPN (from ~/frootvpn directory)
cd ~/frootvpn
sudo openvpn --config "United States - Virginia.ovpn" --auth-user-pass auth.txt --daemon --log /tmp/openvpn.log

# Verify VPN is connected
curl ifconfig.me  # Should show 74.115.214.142 (not baseline 136.61.20.173)

# Stop VPN
sudo killall openvpn
```

### Running the Scraper

**Prerequisites:**
1. VPN connected (see above)
2. PostgreSQL running: `sudo service postgresql start`
3. CapSolver API key in `.env`

```bash
# Test with small limit
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-01-31 \
  --test \
  --limit 1

# Full scrape (after testing)
PYTHONPATH=$(pwd) venv/bin/python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-12-31
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
- `scraper/captcha_solver.py` - reCAPTCHA solving (CapSolver API)
- `scraper/page_parser.py` - Kendo UI Grid HTML parsing
- `scraper/portal_interactions.py` - Form filling and navigation
- `scraper/portal_selectors.py` - CSS selectors for portal elements

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
- **VPN must be on:** Scraper will exit if VPN not detected (baseline IP: 136.61.20.173, VPN IP: 74.115.214.142)
- **PostgreSQL must be running:** `sudo service postgresql start`
- **Portal uses Kendo UI:** Grid, dropdowns, and pagination all use Kendo components
- **Headless mode issues:** Use `headless=False` for development due to aggressive CAPTCHA detection

## Known Issues

1. **Kendo dropdown timeouts:** Status and case type dropdowns timing out after 10s (county works via JS fallback)
2. **CAPTCHA solving delays:** CapSolver API can be slow, adjust timeouts if needed
3. **Browser detection:** Automated browsers trigger image CAPTCHAs instead of checkbox

## Documentation

- `docs/KENDO_GRID_FIXES.md` - Kendo UI implementation details (Nov 24, 2025)
- `docs/SESSION_SUMMARY.md` - Previous session summary
- `docs/SETUP.md` - Detailed setup instructions
- `docs/plans/2025-11-24-nc-foreclosures-architecture-design.md` - Full architecture
- `docs/plans/2025-11-24-phase1-foundation-implementation.md` - Phase 1 plan
- `PROJECT_REQUIREMENTS.md` - Original requirements
