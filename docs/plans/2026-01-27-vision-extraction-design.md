# Vision Extraction for Upset Bid Cases

**Date:** 2026-01-27
**Status:** Approved
**Goal:** Replace Tesseract OCR with Claude Vision for upset_bid cases to eliminate data quality issues (incorrect addresses, bid amounts)

## Overview

Tesseract OCR produces unreliable data due to poor scan quality and handwritten text. Claude Vision understands documents semantically and can extract structured data with high accuracy.

**Key insight:** Data quality only matters when we're making decisions - during the upset bid period. For `upcoming` cases, Tesseract is good enough for tracking.

## Architecture

### Tiered Extraction Strategy

| Case Status | Extraction Method | Rationale |
|-------------|-------------------|-----------|
| `upcoming` | Tesseract (existing) | Rough tracking, cost-free |
| `upset_bid` | Claude Vision | Decision-critical, accuracy required |
| `blocked`, `closed_*` | Tesseract (existing) | Historical, no active decisions |

### Trigger Points

1. **Classification change to `upset_bid`**
   - Hook into existing `_trigger_enrichment_async()` in `classifier.py`
   - Queue Vision sweep of ALL documents for that case

2. **New document during upset period**
   - Modify `process_document()` in `ocr/processor.py`
   - Check `case.classification` - if `upset_bid`, use Vision instead of Tesseract

### Flow Diagrams

**Case enters upset_bid:**
```
Case enters upset_bid status
    ↓
_trigger_enrichment_async() fires (existing)
    ↓
queue_vision_extraction(case_id, all_documents=True)
    ↓
Process each document with Vision
    ↓
Update case with extracted data
```

**New document during upset_bid:**
```
New document downloaded for upset_bid case
    ↓
process_document() checks case.classification
    ↓
If upset_bid → vision_extract() instead of Tesseract
    ↓
Update case with extracted data
```

## Vision Extraction Schema

Claude Vision returns structured JSON for each document:

```python
{
    # Property identification
    "property_address": str,        # Full street address with city/state/zip
    "legal_description": str,       # Lot/block/subdivision info

    # Financial
    "bid_amount": float,            # Current/winning bid (dollars)
    "minimum_next_bid": float,      # Minimum to upset (if shown)
    "deposit_required": float,      # Required deposit (if shown)

    # Dates
    "sale_date": str,               # When auction occurred (YYYY-MM-DD)

    # Parties
    "trustee_name": str,            # Substitute trustee conducting sale
    "attorney_name": str,           # Foreclosure attorney
    "attorney_phone": str,          # Contact phone
    "attorney_email": str,          # Contact email

    # Metadata
    "document_type": str,           # What Vision thinks this doc is
    "confidence": str,              # "high" / "medium" / "low"
    "notes": str                    # Anything unusual Vision noticed
}
```

**Null handling:** Vision returns `null` for missing fields. Only non-null values overwrite case data.

## Relationship with AI Overview

Vision extraction and AI Overview are **complementary, not redundant**:

| Aspect | Vision Extraction | AI Overview |
|--------|-------------------|-------------|
| **Purpose** | Extract clean structured data | Narrative analysis + risk assessment |
| **Runs when** | Per document, immediately | Once per case, queued |
| **Output** | 8-10 data fields | 5-section narrative + financials + red flags |

**Flow:** Vision extracts clean data → AI Overview uses it as baseline → flags any remaining discrepancies.

## Tracking

Add column to `documents` table:

```sql
ALTER TABLE documents ADD COLUMN vision_processed_at TIMESTAMP;
```

| Scenario | Action |
|----------|--------|
| `vision_processed_at` is NULL | Needs Vision processing |
| `vision_processed_at` is set | Already processed, skip |
| Case enters upset_bid | Process all docs where NULL |
| New doc during upset_bid | Process immediately |

**Why timestamp:** Enables re-processing ("anything before date X"), auditing, and future model tracking.

## One-Time Backfill

**Script:** `scripts/backfill_vision_extraction.py`

1. Query all cases WHERE classification = 'upset_bid'
2. For each case, get documents WHERE vision_processed_at IS NULL
3. Run Vision extraction on each document
4. Update case record, set timestamp
5. Log results and cost

**Estimated cost:** 39 cases × ~5 docs × $0.02 = ~$4-5

**Data merge:** Vision values overwrite Tesseract values. Nulls don't overwrite (preserve existing).

## Error Handling

| Scenario | Handling |
|----------|----------|
| Vision API failure | Retry 2x with backoff, then leave NULL for retry later |
| Empty/corrupted PDF | Set timestamp anyway, log "no extractable content" |
| Multi-page docs | Send first 3 pages + last page |
| Conflicting data | Later documents win (except address: first-set-wins) |

**Cost guardrails:**
- Log cost per extraction
- Daily cost cap configurable (default: $10/day)
- Alert if approaching cap

## Cost Estimates

| Scenario | Volume | Cost |
|----------|--------|------|
| Backfill (one-time) | 39 cases × ~5 docs | ~$4-5 |
| Ongoing monthly | ~10-20 new upset_bid cases × ~5 docs | ~$5-10/month |
| New docs during upset | ~2-3 docs/case during period | Included above |

**Total ongoing:** ~$5-20/month for Vision-quality data on all decision-critical cases.

## Implementation Files

| File | Changes |
|------|---------|
| `ocr/vision_extraction.py` | New - Vision API wrapper with structured extraction |
| `ocr/processor.py` | Modify - check classification, route to Vision |
| `extraction/classifier.py` | Modify - add Vision sweep to enrichment trigger |
| `database/models.py` | Add `vision_processed_at` column |
| `scripts/backfill_vision_extraction.py` | New - one-time backfill script |

## Success Criteria

1. All upset_bid cases have Vision-extracted data
2. Zero incorrect addresses on upset_bid cases (currently main pain point)
3. Bid amounts match event portal data (Vision validates)
4. Cost stays under $20/month ongoing
