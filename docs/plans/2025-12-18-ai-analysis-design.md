# AI Analysis Module Design

**Date:** 2025-12-18
**Branch:** feature/ai-analysis
**Status:** Approved

## Overview

Automated AI analysis of foreclosure cases when they transition from `upcoming` to `upset_bid` status. Analysis runs once per case (not on each subsequent upset bid).

## Trigger & Queue

- **Trigger:** Case transitions to `upset_bid` classification
- **Queue:** Database-backed (no Redis/RabbitMQ needed)
- **Processing:** Separate scheduled task runs every 5-10 minutes, processes pending cases one at a time
- **Documents:** All documents with OCR text analyzed (no filtering initially)
- **Contribution tracking:** Per-document tracking to identify valuable document types over time

## Model

- **Claude Sonnet** (`claude-sonnet-4-20250514`)
- Estimated cost: ~$0.01-0.03 per case
- Balanced quality and cost for ~1-5 cases/day volume

## Analysis Outputs

| # | Output | Display Location | Description |
|---|--------|------------------|-------------|
| 1 | **Case Summary** | AI Analysis section | Plain-language summary of the foreclosure case |
| 2 | **Financial Deep Dive** | AI Analysis section | Mortgage amounts, lender names, liens, taxes, judgments. Explicitly notes gaps ("No second mortgage info found") |
| 3 | **Red Flags** | AI Analysis section | Procedural, financial, and property red flags |
| 4 | **Data Confirmation** | AI Analysis section | Flagged discrepancies with review actions |
| 5 | **Deed Book & Page** | Stored only | For future Deed link feature |
| 6 | **Defendant Name** | Parties tile | Extracted and compared against parties table |

### Red Flag Categories

**Procedural:**
- Bankruptcy filings mentioned
- Multiple postponements/continuances
- Contested foreclosure (defendant fighting it)
- Missing required notices or documents

**Financial:**
- Unusually low bid (possible deficiency)
- Multiple liens mentioned
- IRS or federal tax liens
- HOA super-lien priority issues

**Property:**
- Tenant-occupied property mentioned
- Property condition issues noted
- Title defects mentioned
- Multiple defendants (complex ownership)

### Financial Deep Dive

Extracts from court filings (not title searches):
- Original mortgage amount (the one being foreclosed)
- Lender/mortgagee name
- Default amount or debt owed
- Second mortgages (if mentioned)
- Tax liens (if mentioned)
- HOA liens
- Judgment liens

**Gap Detection:** AI explicitly notes what information is NOT found in documents (e.g., "No second mortgage info found", "Tax lien status unknown").

### Discrepancy Handling

- All discrepancies flagged for human review (no auto-correction initially)
- Fields compared: property address, current bid, min next bid, defendant name
- Two review actions:
  - **"Accept AI Value"** - Updates database with AI-extracted value
  - **"Keep Current"** - Marks as reviewed, no database change

## Database Schema

### New Table: `case_analyses`

```sql
CREATE TABLE case_analyses (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id) ON DELETE CASCADE,

    -- Analysis outputs
    summary TEXT,
    financials JSONB,  -- {mortgage_amount, lender, liens: [], taxes, judgments, gaps: []}
    red_flags JSONB,   -- [{category, description, severity}]
    defendant_name VARCHAR(255),
    deed_book VARCHAR(50),
    deed_page VARCHAR(50),

    -- Discrepancy tracking
    discrepancies JSONB,  -- [{field, db_value, ai_value, status, resolved_at, resolved_by}]

    -- Document contribution tracking (detailed)
    document_contributions JSONB,  -- [{document_id, document_name, contributed_to: [], key_extractions: []}]

    -- Metadata
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    model_used VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents INTEGER,
    requested_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX idx_case_analyses_status ON case_analyses(status);
CREATE INDEX idx_case_analyses_case_id ON case_analyses(case_id);
```

## Architecture

### File Structure

```
analysis/
  __init__.py
  analyzer.py        # Main orchestrator - runs analysis on a case
  prompt_builder.py  # Builds Claude prompt with documents + instructions
  queue_processor.py # Scheduled job to process pending analyses
  models.py          # CaseAnalysis SQLAlchemy model
```

### Processing Flow

1. **Trigger:** `case_monitor.py` detects case transition to `upset_bid` → inserts row into `case_analyses` with `status='pending'`

2. **Queue processor** (runs every 5-10 min or after monitoring):
   - Queries `case_analyses WHERE status='pending' ORDER BY requested_at`
   - For each case: calls `analyzer.analyze_case(case_id)`

3. **Analyzer:**
   - Fetches all documents with OCR text for the case
   - Builds prompt with document contents + extraction instructions
   - Calls Claude Sonnet API
   - Parses structured response into 6 outputs
   - Compares confirmations against DB values → generates discrepancies
   - Updates `case_analyses` with results

4. **Frontend:**
   - Case Detail page shows "AI Analysis" section (summary, financials, red flags, discrepancies)
   - Discrepancy review: "Accept AI Value" / "Keep Current" buttons
   - Parties tile shows AI-extracted defendant name

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cases/<id>/analysis` | Fetch analysis results for a case |
| POST | `/api/cases/<id>/analysis/discrepancies/<index>/resolve` | Resolve a discrepancy (accept/reject) |

### GET /api/cases/<id>/analysis

Response:
```json
{
  "status": "completed",
  "summary": "...",
  "financials": {
    "mortgage_amount": 245000,
    "lender": "Wells Fargo",
    "liens": [],
    "gaps": ["No second mortgage info found"]
  },
  "red_flags": [
    {"category": "financial", "description": "Multiple liens mentioned", "severity": "medium"}
  ],
  "discrepancies": [
    {"field": "property_address", "db_value": "123 Main St", "ai_value": "123 Main Street", "status": "pending"}
  ],
  "defendant_name": "John Doe",
  "deed_book": "1234",
  "deed_page": "567",
  "completed_at": "2025-12-18T10:30:00Z",
  "cost_cents": 2
}
```

### POST /api/cases/<id>/analysis/discrepancies/<index>/resolve

Request:
```json
{
  "action": "accept"  // or "reject"
}
```

## Frontend UI

### AI Analysis Section (Case Detail Page)

Located on Case Detail page, contains:

1. **Summary Card** - Plain text case summary
2. **Financials Card** - Structured financial info with gap indicators
3. **Red Flags Card** - List of flags with severity badges
4. **Discrepancy Review Card** - Table of discrepancies with action buttons

### Parties Tile Update

Add AI-extracted defendant name (if different from existing parties data, show both with indicator).

## Future Enhancements

- **Auto-correction:** Once discrepancy review proves AI is trustworthy, enable automatic DB updates for high-confidence matches
- **Document filtering:** Use contribution tracking data to filter out low-value document types
- **Deed link:** Use extracted deed_book/deed_page to generate county deed lookup URLs
- **Analysis dashboard:** Global view of all analyzed cases, pending reviews, cost tracking
