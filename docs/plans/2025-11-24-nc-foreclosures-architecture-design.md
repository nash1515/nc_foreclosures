# NC Foreclosures System - Architecture Design

**Date:** 2025-11-24
**Status:** Approved for Implementation

## Overview

A web scraping and data management system for tracking foreclosure cases across 6 North Carolina counties (Chatham, Durham, Harnett, Lee, Orange, Wake). The system scrapes case data from the NC Online Courts Portal, processes PDFs with OCR, classifies cases, runs AI analysis on actionable opportunities, and provides a web interface for research and bidding strategy.

## System Architecture

### Project Structure

```
nc_foreclosures/
├── scraper/              # Web scraping module
│   ├── initial_scrape.py
│   ├── daily_scrape.py
│   ├── captcha_solver.py
│   ├── vpn_manager.py
│   └── page_parser.py
├── database/             # Database models and access
│   ├── models.py         # SQLAlchemy ORM models
│   ├── schema.sql        # PostgreSQL schema
│   └── connection.py     # DB connection handling
├── ocr/                  # PDF processing and OCR
│   ├── processor.py
│   └── text_extractor.py
├── analysis/             # AI analysis module
│   ├── extractor.py      # Structured data extraction
│   ├── classifier.py     # Upcoming vs upset bid classification
│   └── ai_analyzer.py    # AI insights for upset bid cases
├── web_app/              # Web application
│   ├── app.py            # Flask main app
│   ├── routes/
│   ├── templates/
│   └── static/
├── common/               # Shared utilities
│   ├── config.py         # Configuration management
│   ├── logger.py         # Logging setup
│   └── utils.py          # Shared helpers
├── data/                 # Data storage
│   └── pdfs/             # Downloaded PDFs (county/case organized)
├── docs/                 # Documentation
│   └── plans/            # Design documents
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables (not in git)
```

### Technology Stack

- **Language:** Python 3.12
- **Database:** PostgreSQL with full-text search
- **Web Scraping:**
  - Playwright (browser automation for search/captcha)
  - requests library (fast HTTP for direct case access)
- **OCR:** Tesseract via pytesseract or cloud service
- **CAPTCHA Solving:** CapSolver Python SDK
- **VPN:** FROOT VPN CLI automation with IP verification
- **Web Framework:** Flask
- **ORM:** SQLAlchemy
- **Scheduling:** APScheduler (added in Phase 5)

## Database Schema

### Core Tables

**`cases`** - Main case information
```sql
- id (primary key)
- case_number (unique, e.g., "24SP000437-910")
- county_code (e.g., "910")
- county_name (e.g., "Wake")
- case_type (e.g., "Foreclosure (Special Proceeding)")
- case_status (e.g., "Pending")
- file_date
- case_url (direct link)
- property_address (extracted)
- current_bid_amount (extracted)
- next_bid_deadline (extracted)
- classification (null, "upcoming", "upset_bid")
- last_scraped_at
- created_at, updated_at
```

**`case_events`** - Timeline of case events
```sql
- id (primary key)
- case_id (foreign key)
- event_date
- event_type
- event_description
- created_at
```

**`documents`** - PDFs and extracted text
```sql
- id (primary key)
- case_id (foreign key)
- document_name
- file_path (relative path to PDF)
- ocr_text (full-text indexed)
- document_date
- created_at
```

**`scrape_logs`** - Audit trail for scraping
```sql
- id (primary key)
- scrape_type ("initial" or "daily")
- county_code
- start_date, end_date
- cases_found, cases_processed
- status ("success", "failed", "partial")
- error_message
- started_at, completed_at
```

**`user_notes`** - User annotations
```sql
- id (primary key)
- case_id (foreign key)
- user_name
- note_text
- created_at
```

**Future:** `ai_insights` table or JSON field in `cases` for AI analysis results

## Module Specifications

### 1. Web Scraper Module

**Approach:** Hybrid - Playwright for navigation/captcha, requests for fast case scraping

#### Initial Scrape Workflow

1. **Pre-flight Checks**
   - Verify VPN connected (check IP changed from baseline)
   - Connect to PostgreSQL
   - Validate CapSolver API key

2. **Configuration**
   - CLI args: `--county wake --start 2024-01-01 --end 2024-12-31 --mode quarterly`
   - Auto-break date ranges into chunks
   - Create scrape_log entry

3. **Search Loop** (per time chunk)
   - Navigate to portal with Playwright
   - Fill search filters (county, Special Proceedings, dates, text like "24SP*")
   - Solve reCAPTCHA via CapSolver
   - Submit search, wait for results
   - Check for "too many results" error → retry with smaller chunks
   - Extract total case count for validation

4. **Results Processing**
   - Handle pagination (10 cases/page)
   - Extract case numbers and URLs
   - Track expected vs collected counts

5. **Case Detail Scraping** (per case)
   - Navigate to case URL
   - Identify if foreclosure (case type or specific events)
   - If not foreclosure → skip
   - If foreclosure → extract all data, events, download PDFs
   - Store in database
   - Trigger OCR processing

6. **Validation & Logging**
   - Verify scraped count matches expected
   - Update scrape_log
   - Report summary

#### Daily Scrape Workflow

- Search current date across all 6 counties
- For new cases: full scrape as above
- For existing cases: access by URL (no captcha), compare events, flag changes
- Update `last_scraped_at` timestamps

### 2. OCR Module

**Process:**
1. PDF saved to: `data/pdfs/{county}/{case_number}/doc_{id}.pdf`
2. Extract text with OCR (Tesseract or cloud service)
3. Store in `documents.ocr_text`
4. Full-text index for search
5. If OCR fails: log error, don't block scraping

### 3. Analysis Module

**Phase 1 - Data Extraction (all cases)**
- Parse case HTML and events
- Extract structured fields:
  - Property address
  - Bid amounts
  - Important dates
  - Party names
- Update `cases` table

**Phase 2 - Classification (all cases)**
- Analyze case events
- Classify as "upcoming" (pre-auction) or "upset_bid" (in 10-day window)
- Update `cases.classification`

**Phase 3 - AI Analysis (upset_bid cases only)**
- Input: case data + events + OCR text
- Generate insights:
  - Property value assessment
  - Bid strategy recommendations
  - Risk factors
  - Timeline summary
- Store results (table or JSON field)
- Triggered on-demand or when classification changes to upset_bid

### 4. Web Application (Flask)

**Dashboard View**
- Summary statistics
- Recent updates from daily scrape
- Quick filters (county, classification, date range)

**Case List View**
- Sortable/filterable table
- Columns: case number, county, address, current bid, deadline, status
- Direct link to court portal case URL
- Search across case numbers, addresses, OCR text
- Click row → case detail

**Case Detail View**
- Full case information
- Timeline of events
- Documents list with download links
- OCR text viewer (searchable)
- **Notes section** (add/edit/delete)
- **AI Analysis section** (run button for upset_bid cases, display results)
- External links (Zillow, county property info)

**User Features**
- Simple authentication (2 users)
- Add notes to cases
- Flag/bookmark cases
- Export filtered results to CSV

**Admin Features**
- View scrape logs
- Manual trigger for daily scrape
- Configure schedule (Phase 5)
- System status dashboard

## Development Phases

### Phase 1 - Foundation
- Set up PostgreSQL database and schema
- Basic scraper with Playwright
- VPN verification
- CapSolver integration
- Test on single county, single month
- Basic data extraction (no AI)

### Phase 2 - Complete Scraper
- Pagination handling
- Error recovery and retry logic
- PDF download and OCR
- Validation and logging
- Daily scrape functionality
- Larger sample testing

### Phase 3 - Analysis Module
- Structured data extractor
- Classification logic
- AI analysis for upset_bid cases
- Accuracy testing and refinement

### Phase 4 - Web Application
- Flask app with all views
- Authentication
- Notes and bookmarking
- External links
- Manual scraper triggers

### Phase 5 - Automation & Polish
- APScheduler integration
- Schedule configuration in web UI
- Performance optimization
- Additional features

## Error Handling Strategy

- **reCAPTCHA failures:** Retry 3x, log failure, continue with next search
- **VPN check failure:** Stop immediately, alert user
- **Scrape errors:** Log error, continue with next case (don't block batch)
- **OCR failures:** Log but don't block (retry later)
- **Database errors:** Stop processing, alert (data integrity critical)
- **Too many results:** Automatically reduce date range and retry

## Configuration Management

**Environment Variables (.env):**
```
DATABASE_URL=postgresql://user:pass@localhost/nc_foreclosures
CAPSOLVER_API_KEY=CAP-06FF6F96A738937699FA99040C8565B3D62AB676B37CC6ECB99DDC955F22E4E2
VPN_BASELINE_IP=<your non-VPN IP>
PDF_STORAGE_PATH=./data/pdfs
LOG_LEVEL=INFO
```

**CLI Arguments (scraper):**
```bash
python scraper/initial_scrape.py \
  --county wake \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --mode quarterly
```

## Key Design Decisions

1. **Monorepo structure** - All modules share common utilities, single dependency management
2. **PostgreSQL** - Scalable, full-text search, good for multi-user web app
3. **Hybrid scraping** - Playwright for captcha/search, requests for speed
4. **Filesystem PDFs** - Scalable storage with paths in DB
5. **Immediate OCR** - Process PDFs as downloaded for searchability
6. **Selective AI analysis** - Only upset_bid cases to manage costs
7. **Configurable scraper** - CLI args for flexible testing and execution
8. **Manual then automated** - Manual execution during development, scheduling added later

## Next Steps

1. Document this design (complete)
2. Set up git worktree for isolated development
3. Create detailed implementation plan
4. Begin Phase 1 implementation
