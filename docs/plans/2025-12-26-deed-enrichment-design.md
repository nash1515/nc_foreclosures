# Deed Enrichment Feature Design

**Date:** 2025-12-26
**Branch:** feature/deed-enrichment
**Status:** Ready for implementation

## Overview

Two-phase feature to extract deed book/page information and provide direct links to county Register of Deeds portals.

### Phase 1: AI Prompt Enhancement
Improve Claude's extraction of deed book/page by explicitly distinguishing from Book of Maps/Plat Book references.

### Phase 2: County Deed Links
Generate and store deed URLs per county, display in Dashboard and Case Detail UI.

## Data Flow

```
Case transitions to upset_bid
    ↓
AI Analysis runs (existing)
    ↓
Claude extracts deed_book + deed_page (improved prompt)
    ↓
After AI analysis completes:
    ↓
Deed Router dispatches to county-specific builder
    ├── Wake (910)    → Direct URL
    ├── Durham (310)  → Playwright automation
    ├── Harnett (420) → Direct URL
    ├── Lee (520)     → Search page URL
    ├── Orange (670)  → Direct URL
    └── Chatham (180) → Search page URL
    ↓
deed_url stored in case_analyses table
    ↓
API returns deed_url with case data
    ↓
Frontend displays in Dashboard Links + Case Detail Quick Links
```

## Phase 1: AI Prompt Enhancement

### Current Prompt (prompt_builder.py lines 218-219)
```
"deed_book": "<deed book number if found, or null>",
"deed_page": "<deed page number if found, or null>",
```

### Enhanced Prompt
```
"deed_book": "<Deed Book number for the property's deed of trust/mortgage - NOT Book of Maps or Plat Book which are for subdivision plats>",
"deed_page": "<Deed Page number corresponding to the Deed Book above>",
```

### Additional Guidance Section
```
## DEED BOOK vs BOOK OF MAPS/PLAT BOOK
- **Deed Book**: Records property ownership transfers and deeds of trust (mortgages). This is what we need.
- **Book of Maps** (Wake County) / **Plat Book** (other counties): Records subdivision plat maps showing lot boundaries. Do NOT extract these.
- Example Deed reference: "recorded in Deed Book 15704, Page 1495"
- Example Plat reference: "as shown on map recorded in Book of Maps 2007, Page 1270" - IGNORE this
- Look for the deed of trust that secures the loan being foreclosed.
```

## Phase 2: County Deed URL Builders

### County URL Formats

| County | Code | Type | URL Format |
|--------|------|------|------------|
| Wake | 910 | Direct | `https://rodrecords.wake.gov/web/web/integration/search?field_BookPageID_DOT_Page={page}&field_BookPageID_DOT_Volume={book}` |
| Durham | 310 | Playwright | Search `rodweb.dconc.gov/web/search/DOCSEARCH5S1`, extract document URL |
| Harnett | 420 | Direct | `https://us6.courthousecomputersystems.com/HarnettNC/Image/ShowDocImage?booktype=Deed&tif2pdf=true&BookNum={book}&PageNum={page}` |
| Orange | 670 | Direct | `https://rod.orangecountync.gov/orangenc/Image/ShowDocImage?booktype=Deed&tif2pdf=true&BookNum={book}&PageNum={page}` |
| Lee | 520 | Search page | `https://www.leencrod.org/search.wgx` (user clicks Book/Page tab) |
| Chatham | 180 | Search page | `https://www.chathamncrod.org/search.wgx` (user clicks Book/Page tab) |

### Module Structure

```
enrichments/
└── deed/
    ├── __init__.py
    ├── router.py           # Routes by county code to appropriate builder
    ├── url_builders.py     # Wake, Harnett, Orange, Lee, Chatham (URL construction)
    └── durham_scraper.py   # Playwright automation for Durham
```

### Router Logic

```python
def build_deed_url(case_number: str, deed_book: str, deed_page: str) -> str | None:
    """
    Route to county-specific URL builder.
    Returns URL or None if book/page missing.
    """
    if not deed_book or not deed_page:
        return None

    county_code = case_number.split('-')[1]  # e.g., "910"

    if county_code == '910':      # Wake
        return build_wake_url(deed_book, deed_page)
    elif county_code == '310':    # Durham - requires separate async call
        return None  # Handled by durham_scraper.py
    elif county_code == '420':    # Harnett
        return build_harnett_url(deed_book, deed_page)
    elif county_code == '520':    # Lee
        return build_lee_url()  # Search page only
    elif county_code == '670':    # Orange
        return build_orange_url(deed_book, deed_page)
    elif county_code == '180':    # Chatham
        return build_chatham_url()  # Search page only

    return None
```

## Database Changes

### New Column
Add to `case_analyses` table:
- `deed_url` VARCHAR(500) - Generated deed lookup URL

### Migration
```sql
-- migrations/add_deed_url.sql
ALTER TABLE case_analyses ADD COLUMN deed_url VARCHAR(500);
```

## API Changes

### `/api/cases/upset-bids` (cases.py)
Include `deed_url` in response for Dashboard display.

### `/api/cases/<case_id>/analysis` (analysis.py)
Include `deed_url` in analysis response (already returns deed_book/deed_page).

## Frontend Changes

### Dashboard.jsx
- Add Deed icon to Links column (alongside RE icons)
- Show when `deed_url` is present
- Tooltip: "View Deed Record"

### CaseDetail.jsx
- Add "Deed" button to Quick Links section
- Display deed_book and deed_page values
- Button disabled with "Coming soon" if no deed_url

### New Component
- `frontend/src/assets/DeedIcon.jsx` - Document/scroll icon

## Integration & Trigger Point

### After AI Analysis
In `analyzer.py` after storing analysis results:

```python
if analysis.deed_book and analysis.deed_page:
    from enrichments.deed.router import build_deed_url
    deed_url = build_deed_url(case.case_number, analysis.deed_book, analysis.deed_page)
    analysis.deed_url = deed_url
    session.commit()
```

### Durham Special Handling
Durham requires Playwright automation - runs separately after AI analysis completes, similar to RE enrichment pattern.

### Backfill Script
`scripts/backfill_deed_urls.py` - Generate URLs for existing cases with deed_book/deed_page populated.

## Files Summary

### New Files
```
enrichments/deed/__init__.py
enrichments/deed/router.py
enrichments/deed/url_builders.py
enrichments/deed/durham_scraper.py
migrations/add_deed_url.sql
scripts/backfill_deed_urls.py
frontend/src/assets/DeedIcon.jsx
```

### Modified Files
```
analysis/prompt_builder.py      # Enhanced deed extraction guidance
analysis/analyzer.py            # Trigger deed URL generation
analysis/models.py              # Add deed_url column (if using model)
web_app/api/cases.py            # Return deed_url in upset-bids
web_app/api/analysis.py         # Return deed_url in analysis
frontend/src/pages/Dashboard.jsx    # Deed icon in Links
frontend/src/pages/CaseDetail.jsx   # Deed button in Quick Links
```

## Testing Plan

1. **Phase 1 Testing:**
   - Re-run AI analysis on sample case
   - Verify deed_book extracted correctly (not Book of Maps)
   - Check Wake County case (has "Book of Maps" terminology)

2. **Phase 2 Testing:**
   - Test each county URL builder with known book/page values
   - Verify direct links open correct documents (Wake, Harnett, Orange)
   - Verify search pages load (Lee, Chatham)
   - Test Durham Playwright automation

3. **Integration Testing:**
   - End-to-end: new case → AI analysis → deed URL generated → displayed in UI
   - Backfill script on existing 7 cases with deed data

## Current State

- **deed_book/deed_page columns:** Already exist in case_analyses
- **Extraction working:** 7/8 cases have deed data (87.5% success rate)
- **No UI display yet:** Data exists but not shown to users
