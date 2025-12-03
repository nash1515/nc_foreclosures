# NC Foreclosures Project

A comprehensive system for tracking and analyzing foreclosure cases across 6 North Carolina counties.

## Overview

This system scrapes foreclosure data from the North Carolina Online Courts Portal, processes documents with OCR, performs AI-powered analysis, and provides a web interface for research and bidding strategy.

**Target Counties:** Chatham, Durham, Harnett, Lee, Orange, Wake

## Features

### Phase 1 - Foundation (✅ Complete)
- PostgreSQL database with full schema
- VPN verification for secure scraping
- CapSolver reCAPTCHA integration
- Playwright-based web scraper framework
- Comprehensive logging and error handling

### Phase 2 - PDF & OCR (✅ Complete)
- PDF downloading from case detail pages
- OCR text extraction (pdftotext + Tesseract fallback)
- Batch scrape script with monthly/quarterly strategies

### Phase 2.5 - Data Extraction (✅ Complete)
- Regex-based structured data extraction from OCR text
- Extracts: property address, bid amounts, legal description, attorney info
- Case classification (upcoming vs upset_bid)
- Auto-triggers after OCR processing

### Phase 3 - AI Analysis (✅ Complete)
- Claude AI integration for edge case analysis
- Case classification (upcoming, upset_bid, blocked, closed_sold, closed_dismissed)
- Investment opportunity scoring

### Phase 4 - Daily Scraping & Scheduler (✅ Complete)
- Automated daily scraper (searches for new cases filed yesterday)
- Case monitoring (tracks existing cases for status changes)
- **Scheduler service** with database-driven configuration
- REST API for frontend schedule management
- Default: 5:00 AM Mon-Fri

### Phase 5 - Enrichment (Planned)
- Zillow property links
- County property record links
- Tax assessment values

### Phase 6 - Web Application (Planned)
- Flask web interface
- Case search and filtering
- Scheduler configuration UI
- Notes and bookmarking
- External resource links

## Quick Start

See [docs/SETUP.md](docs/SETUP.md) for detailed installation instructions.

```bash
# Clone repository
git clone https://github.com/nash1515/nc_foreclosures.git
cd nc_foreclosures

# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up database
sudo service postgresql start
PYTHONPATH=$(pwd) venv/bin/python database/init_db.py

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run tests
PYTHONPATH=$(pwd) venv/bin/python tests/test_phase1_integration.py
```

## Project Structure

```
nc_foreclosures/
├── common/          # Shared utilities (config, logging, county codes)
├── database/        # PostgreSQL models and connection management
├── scraper/         # Web scraping (VPN, CAPTCHA, Playwright, PDF download)
├── scheduler/       # Automated job scheduling (API-configurable)
├── ocr/             # PDF processing and text extraction
├── extraction/      # Structured data extraction and classification
├── analysis/        # AI analysis (Claude integration)
├── web_app/         # Flask web application (Phase 6)
├── scripts/         # Helper scripts (scheduler_control.sh, run_daily.sh)
├── tests/           # Integration and unit tests
├── data/pdfs/       # Downloaded PDF storage (gitignored)
└── docs/            # Documentation and implementation plans
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Installation and configuration
- [Architecture Design](docs/plans/2025-11-24-nc-foreclosures-architecture-design.md) - System architecture
- [Phase 1 Implementation Plan](docs/plans/2025-11-24-phase1-foundation-implementation.md) - Foundation details
- [Project Requirements](PROJECT_REQUIREMENTS.md) - Complete specifications

## Development Status

**Current Phase:** Daily Operations - Scheduler Active

**Completed:**
- Phase 1: Foundation (database, VPN, CAPTCHA, scraper framework)
- Phase 2: PDF downloading and OCR processing
- Phase 2.5: Structured data extraction and case classification
- Phase 3: AI analysis with Claude integration
- Phase 4: Daily scraping with automated scheduler
- Initial Scrape: All 6 counties, 2020-2025
- Retry Session: All failed date ranges completed

**Database Status (as of Dec 3, 2025):**
| Metric | Count |
|--------|-------|
| Total Cases | 1,724 |
| Upcoming | 1,372 |
| Upset Bid (Active) | 24 |
| Closed (Sold) | 183 |
| Blocked (Bankruptcy) | 77 |
| Closed (Dismissed) | 53 |

- All 6 counties tracked (Wake, Durham, Harnett, Lee, Orange, Chatham)
- Scheduler runs daily at 5 AM Mon-Fri

**Next Steps:**
1. ~~Implement daily scrape functionality~~ ✅ Complete
2. ~~Set up automated scheduler~~ ✅ Complete
3. Build frontend web application
4. Build enrichment module for external data (Zillow, county records)

## Technology Stack

- **Language:** Python 3.12
- **Database:** PostgreSQL 16
- **Web Scraping:** Playwright, BeautifulSoup4
- **CAPTCHA:** CapSolver API
- **VPN:** FrootVPN (OpenVPN) - optional
- **ORM:** SQLAlchemy
- **OCR:** pdftotext (poppler-utils), Tesseract
- **AI:** Anthropic Claude API
- **Scheduler:** Custom Python service with systemd
- **Web Framework:** Flask (Phase 6)

## Contributing

This is a private project. All development by nash1515 with assistance from Claude Code.

## License

Private - All Rights Reserved

## Repository

https://github.com/nash1515/nc_foreclosures
