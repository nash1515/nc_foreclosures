# Phase 3: AI Analysis Module Design

**Date:** 2025-11-27
**Status:** Approved
**Branch:** `feature/phase3-ai-analysis`

## Overview

AI-powered analysis of foreclosure cases to verify upset bid status, calculate deadlines, extract financial information, and flag items requiring research.

## Scope

- **Target cases:** Upset bid cases only (~91 initial, plus new cases from daily scrape)
- **Model:** Claude Opus (best reasoning for legal document analysis)
- **Cost estimate:** ~$68 initial batch, ~$1-5/day ongoing

## Triggers

Analysis runs when:
1. Case enters `upset_bid` classification (first time)
2. Significant new events detected on existing upset_bid cases:
   - "Upset Bid Filed" (deadline extension)
   - Bankruptcy-related filings
   - Sale confirmed/cancelled/vacated
   - Any document on a case with prior status blockers

## Data Flow

```
[Case enters upset_bid]
    → Query case info, events, parties from DB
    → Filter documents through skip list
    → Batch OCR text (smart batching if >100K tokens)
    → Build prompt with knowledge base rules
    → Call Claude Opus API
    → Parse hybrid JSON response
    → Store in ai_analysis table
    → If status blockers found → Update case classification
    → Aggregate document evaluations → Update skip list
```

## Input Assembly

### Structured Data (from database)
- Case info: case_number, file_date, status, style
- All events: date, type, filed_by (for validation)
- Party info: respondents, petitioners, trustees
- Existing extraction data: property_address, current_bid, etc.

### OCR Text (from documents)
- All documents for the case, filtered through skip list
- Each document labeled with header: `=== DOCUMENT: filename.pdf (filed MM/DD/YYYY) ===`
- Smart batching if total exceeds ~100K tokens

## Output Format

Hybrid JSON with structured fields plus free-form analysis:

```json
{
  "is_valid_upset_bid": true,
  "status_blockers": [],
  "recommended_classification": "upset_bid",

  "upset_deadline": "2025-12-05",
  "deadline_extended": false,
  "extension_count": 0,

  "current_bid_amount": 185000.00,
  "estimated_total_liens": 245000.00,
  "mortgage_info": [
    {"holder": "Bank of America", "amount": 220000, "rate": "4.5%", "date": "2019-03-15"}
  ],
  "tax_info": {
    "outstanding": 3500,
    "year": 2024,
    "county_assessed_value": 275000
  },

  "research_flags": [
    {"type": "irs_lien", "description": "Federal tax lien recorded 2023-06-01", "severity": "high"},
    {"type": "multiple_mortgages", "description": "Second mortgage holder identified", "severity": "medium"}
  ],

  "document_evaluations": [
    {"doc_id": 123, "useful": true, "doc_type": "Notice of Sale", "reason": "Contains sale date and bid amount"},
    {"doc_id": 124, "useful": false, "doc_type": "Certificate of Service", "reason": "Procedural only"}
  ],

  "analysis_notes": "Property appears to be in valid upset bid period. Sale occurred 11/25/2025 with winning bid of $185,000. First mortgage balance exceeds sale price, suggesting no equity for junior lienholders. IRS lien should be researched - may have redemption rights.",

  "confidence_score": 0.85,

  "discrepancies": [
    {"field": "sale_date", "expected": "11/25/2025", "found": "11/24/2025 in one document"}
  ]
}
```

## Database Schema

### New table: `ai_analysis`

```sql
CREATE TABLE ai_analysis (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id),
    analyzed_at TIMESTAMP DEFAULT NOW(),
    model_version VARCHAR(50),

    -- Status verification
    is_valid_upset_bid BOOLEAN,
    status_blockers JSONB,
    recommended_classification VARCHAR(50),

    -- Deadline info
    upset_deadline DATE,
    deadline_extended BOOLEAN,
    extension_count INTEGER DEFAULT 0,

    -- Financial summary
    current_bid_amount DECIMAL(12,2),
    estimated_total_liens DECIMAL(12,2),
    mortgage_info JSONB,
    tax_info JSONB,

    -- Research flags
    research_flags JSONB,

    -- Document usefulness tracking
    document_evaluations JSONB,

    -- Free-form
    analysis_notes TEXT,
    confidence_score DECIMAL(3,2),
    discrepancies JSONB,

    -- Audit
    tokens_used INTEGER,
    cost_estimate DECIMAL(8,4)
);

CREATE INDEX idx_ai_analysis_case_id ON ai_analysis(case_id);
CREATE INDEX idx_ai_analysis_analyzed_at ON ai_analysis(analyzed_at);
```

### New table: `document_skip_patterns`

```sql
CREATE TABLE document_skip_patterns (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(50),
    pattern VARCHAR(255),
    skip_count INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT NOW(),
    added_by VARCHAR(50)
);
```

## Knowledge Base (Tiered)

### Tier 1: Core Rules (~500 tokens, always included)

```
NC FORECLOSURE UPSET BID RULES:
- Upset bid period: 10 calendar days from Report of Sale filing
- Each new upset bid restarts the 10-day clock
- Minimum increase: 5% of prior bid OR $750, whichever is greater
- Required deposit: 5% of bid amount (minimum $750)
- If 10th day falls on weekend/holiday: extends to next business day
- Bankruptcy filing = automatic stay (case not valid for bidding)
- Military service = 90-day protection (SCRA + NC GS 45-21.23)
```

### Tier 2: Lookup Tables (~300 tokens, always included)

```
LIEN_PRIORITY (highest to lowest):
1. Local property taxes (super-priority, survives foreclosure)
2. State tax liens
3. Federal IRS liens (may have redemption rights)
4. First mortgage/deed of trust
5. Junior liens in recording order
6. HOA liens (extinguished by foreclosure of prior deed of trust)

STATUS_BLOCKERS (invalidate upset bid period):
- bankruptcy_filed
- military_service
- relief_from_stay_granted
- sale_vacated
- sale_cancelled
- appeal_pending

KEY_EVENTS:
- "Report of Sale" / "Report Of Foreclosure Sale" → starts upset period
- "Upset Bid Filed" → extends deadline 10 days
- "Bankruptcy" / "Notice of Bankruptcy" → automatic stay
- "Dismissed" / "Voluntary Dismissal" → case closed
```

### Tier 3: Full Statute Reference (stored in file, retrieved on demand)

File: `analysis/nc_foreclosure_law.md`

Contains complete text of:
- NC GS 45-21.27 (Upset bid procedures)
- NC GS 45-21.26 (Report of Sale requirements)
- NC GS Article 2A (Power of sale foreclosure)
- 11 USC 362 (Bankruptcy automatic stay)
- Lien priority statutes

Sources:
- https://www.ncleg.gov/Laws/GeneralStatuteSections/Chapter45
- https://ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_45/Article_2A.html
- https://www.law.cornell.edu/uscode/text/11/362

## Module Architecture

```
analysis/
├── __init__.py
├── nc_foreclosure_law.md       # Tier 3: Full statute reference
├── knowledge_base.py           # Tier 1+2: Compact rules for prompts
├── prompt_builder.py           # Assembles prompts from case data
├── case_analyzer.py            # Main analysis orchestrator
├── document_filter.py          # Skip list management
├── api_client.py               # Claude API wrapper
└── run_analysis.py             # CLI entry point
```

### Component Responsibilities

**`knowledge_base.py`**
- `get_core_rules()` → Returns Tier 1 text
- `get_lookup_tables()` → Returns Tier 2 structured data
- `get_full_statute(section)` → Returns Tier 3 on-demand

**`prompt_builder.py`**
- `build_prompt(case_id)` → Assembles complete prompt
- Gathers case info, events, parties from DB
- Filters documents through skip list
- Batches OCR text if exceeding token limit
- Combines with knowledge base rules

**`case_analyzer.py`**
- `analyze_case(case_id)` → Full analysis pipeline
- `analyze_pending()` → Process all cases needing analysis
- Calls prompt builder → API → parses response
- Saves to `ai_analysis` table
- Updates case classification if status blockers found
- Aggregates document evaluations for skip list

**`document_filter.py`**
- `should_skip(document)` → Check against skip list
- `add_pattern(pattern_type, pattern)` → Add new skip pattern
- `update_from_evaluations(evaluations)` → Learn from AI feedback

**`api_client.py`**
- `call_claude(prompt, model="opus")` → API wrapper
- Handles retries, rate limiting, token counting
- Returns parsed JSON response

**`run_analysis.py`**
- CLI entry point
- `--case CASE_NUMBER` → Analyze specific case
- `--pending` → Analyze all pending upset_bid cases
- `--dry-run` → Preview without API calls
- `--limit N` → Limit batch size

## Analysis Categories

### Status Blockers (Classification Corrections)
Things that mean case is NOT in valid upset bid period:
- Bankruptcy filed after Report of Sale
- Sale vacated or cancelled
- Appeal pending
- Military service protection active

If found: Update case classification, flag for review.

### Research Flags (Homework Items)
Things requiring further investigation:
- IRS/federal tax liens (redemption rights)
- Multiple mortgage holders
- Large outstanding property taxes
- Unusual title history
- Junior lien complexity

These don't disqualify the property but affect bid strategy.

## Document Learning

The AI evaluates each document's usefulness:
- `useful: true` → Contains actionable information
- `useful: false` → Procedural/routine filing

Over time, patterns emerge:
- "Certificate of Service" → Always skip
- "Affidavit of Mailing" → Always skip
- "Notice of Sale" → Always include
- "Report of Sale" → Always include

Skip patterns reduce token usage and cost for future analyses.

## Re-Analysis Triggers

Smart re-analysis when significant events occur:
1. New "Upset Bid Filed" event → Deadline extended
2. New bankruptcy filing → Status blocker
3. Sale confirmed/cancelled → Status change
4. New document on case with prior blockers → Re-evaluate

Avoids unnecessary API costs for routine filings.

## Usage

```bash
# Analyze specific case
PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --case 24SP001234-910

# Analyze all pending upset_bid cases
PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --pending

# Dry run (preview without API calls)
PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --pending --dry-run

# Limit batch size
PYTHONPATH=$(pwd) venv/bin/python analysis/run_analysis.py --pending --limit 10
```

## Cost Estimates

| Scenario | Cases | Tokens/Case | Cost |
|----------|-------|-------------|------|
| Initial batch | 91 | ~50K | ~$68 |
| Daily new cases | 1-3 | ~50K | ~$1-3 |
| Re-analysis (events) | 0-2 | ~50K | ~$0-2 |

## Success Criteria

1. Correctly identify status blockers (no false positives on valid cases)
2. Calculate upset deadlines within 1 day accuracy
3. Extract financial info from 80%+ of cases with mortgage docs
4. Document skip list reduces average tokens by 30% after initial batch
5. Discrepancy detection catches OCR/event data mismatches

## Next Steps

1. Create `analysis/` module structure
2. Implement knowledge base with tiered rules
3. Build prompt builder with smart batching
4. Create API client with Claude integration
5. Implement document filter learning
6. Run on test cases, validate output
7. Process full upset_bid batch
8. Integrate with daily scrape pipeline
