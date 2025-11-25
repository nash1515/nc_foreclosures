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

### Phase 2 - Complete Scraper (Planned)
- PDF downloading
- OCR text extraction
- Daily scrape automation
- Error recovery and retry logic

### Phase 3 - Analysis (Planned)
- Structured data extraction
- Case classification (upcoming vs upset bid)
- AI-powered insights for actionable cases

### Phase 4 - Web Application (Planned)
- Flask web interface
- Case search and filtering
- Notes and bookmarking
- External resource links

### Phase 5 - Automation (Planned)
- Scheduled daily scrapes
- Performance optimization
- Additional features

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
├── scraper/         # Web scraping (VPN, CAPTCHA, Playwright)
├── ocr/            # PDF processing and text extraction
├── analysis/       # Data extraction and AI analysis
├── web_app/        # Flask web application
├── tests/          # Integration and unit tests
├── data/pdfs/      # Downloaded PDF storage
└── docs/           # Documentation and implementation plans
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Installation and configuration
- [Architecture Design](docs/plans/2025-11-24-nc-foreclosures-architecture-design.md) - System architecture
- [Phase 1 Implementation Plan](docs/plans/2025-11-24-phase1-foundation-implementation.md) - Foundation details
- [Project Requirements](PROJECT_REQUIREMENTS.md) - Complete specifications

## Development Status

**Current Phase:** Phase 1 Foundation - ✅ Complete

**Next Steps:**
1. Explore NC Courts Portal to identify HTML structure
2. Implement portal-specific parsing logic
3. Test scraper with small samples
4. Begin Phase 2: PDF downloading and OCR

## Technology Stack

- **Language:** Python 3.12
- **Database:** PostgreSQL 16
- **Web Scraping:** Playwright, BeautifulSoup4
- **CAPTCHA:** CapSolver API
- **VPN:** FROOT VPN
- **ORM:** SQLAlchemy
- **Web Framework:** Flask (Phase 4)

## Contributing

This is a private project. All development by nash1515 with assistance from Claude Code.

## License

Private - All Rights Reserved

## Repository

https://github.com/nash1515/nc_foreclosures
