# Session History

Detailed session-by-session history for NC Foreclosures project. This file preserves context for debugging and understanding past decisions.

## Dec 13, 2025 - Session 4

### Focus: OCR/Extraction Pipeline Reliability

### Root Cause Analysis
Conducted systematic debugging to identify why OCR and extraction were not completing:

1. **OCR skip logic** - Documents with any ocr_text (even empty) were skipped on retry
2. **Extraction coupling** - Extraction only triggered by OCR completion, no independent retry
3. **Conditional OCR tasks** - Task 1.5 skipped when `cases_processed == 0`
4. **Selective document OCR** - Only upset_bid/sale documents were OCR'd
5. **Silent error handling** - 9+ bare `except:` blocks swallowing failures
6. **No extraction tracking** - No way to identify documents needing extraction

### Fixes Implemented

| Fix | File(s) | Change |
|-----|---------|--------|
| 1 | `ocr/processor.py` | Return False for <50 chars, allow retry |
| 2 | `database/models.py`, `extractor.py` | Added `extraction_attempted_at` tracking |
| 3 | `scraper/daily_scrape.py` | Removed `cases_processed > 0` condition |
| 4 | `scraper/case_monitor.py` | OCR all documents, not just upset_bid/sale |
| 5 | 3 files | Replaced 9 bare `except:` with logging |
| 6 | `extractor.py` | Added `get_documents_needing_extraction()` |

### Database Changes
- Added `extraction_attempted_at` column to documents table
- Added partial index `idx_documents_extraction_pending`
- Deleted 68 orphaned document records (files never existed)

### Commits
- `5bed81b` - fix: improve OCR/extraction reliability with 6 targeted fixes

### Results
- All 37 upset_bid cases: 100% complete data (address, bid, sale_date, deadline)
- All documents in upset_bid cases: 100% OCR coverage
- Orphaned documents: 188 → 0

## Session 22 (Dec 8, 2025) - Critical Upset Bid Bug Fixes

**Fixed 7 bugs in upset bid classification:**

1. **Event date extraction** (`case_monitor.py`): Was using NULL dates from HTML-parsed party events; now queries DB for actual "Upset Bid Filed" event dates
2. **Classifier order of operations** (`classifier.py`): Now checks recent upset bid events BEFORE checking stale deadline
3. **PDF extraction gate removed** (`case_monitor.py`): Now runs for any case with upset events, not just those already classified
4. **Stale reclassification** (`classifier.py`): Now updates deadline from recent events instead of wrongly reclassifying to closed_sold
5. **Event whitespace comparison** (`case_monitor.py`): Added .strip() to fix event deduplication
6. **download_case_documents args** (`date_range_scrape.py`): Fixed to pass all 4 required arguments
7. **SQLAlchemy session error** (`classifier.py`): Query within existing session context

**Key insight:** Party events ("Upset Bidder") have NULL event_date - must query DB for "Upset Bid Filed" events.

**New module:** `common/business_days.py` - NC court holiday calendar for deadline calculation per NC G.S. 45-21.27

## Session 21 (Dec 6, 2025) - Address Extraction Enhancement

- Added 6 new address patterns for HOA and lien foreclosures
- Attorney address filtering to prevent false positives
- Results: 10 new addresses extracted, 1 incorrect cleared, 61.6% coverage

## Session 20 (Dec 5, 2025) - Dashboard Implementation

- Dashboard component with stats cards, classification/county breakdowns
- Upset bid opportunities table with urgency color coding
- New API endpoints: `/api/cases/stats`, `/api/cases/upset-bids`

## Session 19 (Dec 5, 2025) - OAuth Fix

- Restored Google OAuth credentials lost from .env file
- Documented git worktree workflow for frontend development

## Session 18 (Dec 4, 2025) - Multi-Document Popup Fix

- Fixed handling of "Document Selector" dialog for events with 2+ documents
- Portal uses native HTML `<dialog>` elements, not `div[role="dialog"]`

## Session 17 (Dec 4, 2025) - Report of Sale Extraction

- Added AOC-SP-301 (Report of Foreclosure Sale) extraction
- All upset_bid cases now have complete bid data
- Daily validation function for upset_bid data quality

## Session 16 (Dec 3, 2025) - Frontend Phase 1

- React + Vite + Ant Design frontend
- Flask API with Google OAuth
- Protected routes, user model

## Session 15 (Dec 3, 2025) - Scheduler Service

- Database-driven scheduler with API configuration
- Default: 5 AM Mon-Fri
- systemd service file for production

## Session 14 (Dec 3, 2025) - Partition Sales

- Expanded case detection to include partition sales (co-owner forced sales)
- Added upset bid opportunity indicators

## Session 13 (Dec 2, 2025) - Bot Detection Fix

- Added Chrome user-agent to all Playwright contexts
- Fixed county detection from case number suffix

## Session 12 (Dec 2, 2025) - Database Completion

- Retry logic with exponential backoff
- Re-scraped 845 cases with NULL event types
- Portal URL format migration

## Session 11 (Dec 1, 2025) - Daily Scraping System

- `daily_scrape.py` orchestrator
- `case_monitor.py` for direct URL access (no CAPTCHA)
- VPN removed (not needed)

## Sessions 9-10 (Nov 30 - Dec 1, 2025) - Classification & AI

- 5 classification states defined
- Claude API integration (haiku model)
- AI guardrails for upset_bid-only analysis

## Sessions 1-8 (Nov 24-27, 2025) - Foundation

- PostgreSQL + SQLAlchemy setup
- Playwright scraper with CapSolver CAPTCHA
- Kendo UI Grid parsing
- All 6 counties scraped (2020-2025)
- OCR and extraction modules
- 1,716 initial cases
