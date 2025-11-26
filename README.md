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

### Phase 3 - AI Analysis (Planned)
- AI-powered insights for edge cases
- Handle complex status changes (bankruptcy, motions)
- Investment opportunity scoring

### Phase 4 - Enrichment (Planned)
- Zillow property links
- County property record links
- Tax assessment values

### Phase 5 - Web Application (Planned)
- Flask web interface
- Case search and filtering
- Notes and bookmarking
- External resource links

### Phase 6 - Automation (Planned)
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
├── scraper/         # Web scraping (VPN, CAPTCHA, Playwright, PDF download)
├── ocr/             # PDF processing and text extraction
├── extraction/      # Structured data extraction and classification
├── analysis/        # AI analysis (Phase 3)
├── web_app/         # Flask web application (Phase 5)
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

**Current Phase:** Initial Scrape - 🔄 In Progress

**Completed:**
- Phase 1: Foundation (database, VPN, CAPTCHA, scraper framework)
- Phase 2: PDF downloading and OCR processing
- Phase 2.5: Structured data extraction and case classification
- Phase 3: Parallel batch scraper with failure tracking

**Scrape Progress (as of Nov 25, 2025):**
- 2020: 130 foreclosure cases scraped
- 2021: 83 foreclosure cases scraped
- Total: **213 foreclosures** in database across 5 counties
- Note: Chatham County temporarily skipped due to portal issues

**Next Steps:**
1. Continue scraping 2022-2025
2. Retry failed date ranges
3. Investigate Chatham County portal issues
4. Implement daily scrape functionality
5. Build enrichment module for external data (Zillow, county records)

## Technology Stack

- **Language:** Python 3.12
- **Database:** PostgreSQL 16
- **Web Scraping:** Playwright, BeautifulSoup4
- **CAPTCHA:** CapSolver API
- **VPN:** FrootVPN (OpenVPN)
- **ORM:** SQLAlchemy
- **OCR:** pdftotext (poppler-utils), Tesseract
- **Web Framework:** Flask (Phase 5)

## Contributing

This is a private project. All development by nash1515 with assistance from Claude Code.

## License

Private - All Rights Reserved

## Repository

https://github.com/nash1515/nc_foreclosures
