# Smart Document Filtering for AI Analysis

**Date:** 2025-12-26
**Branch:** feature/deed-enrichment
**Status:** Ready for implementation

## Problem

When a case has many documents (300+), the AI analyzer exceeds Claude's 200K token limit and fails. Two cases failed:
- 25SP000393-420: 309 documents, 208,660 tokens
- 25SP000628-310: 324 documents, 204,588 tokens

The deed book/page information IS present in the documents but Claude never sees it because the API rejects the oversized prompt.

## Solution

Add intelligent document selection to `analysis/prompt_builder.py`:
1. **Deduplicate** - Hash OCR text, skip documents with identical content
2. **Prioritize** - Sort by document type importance
3. **Budget** - Stop adding documents at 150K tokens (~600K chars)

## Document Priority Tiers

**Tier 1 (Highest - Always Include):**
- Notice of Hearing on Foreclosure
- Deed of Trust
- Notice of Sale/Resale
- Original case filing document (matches case number)

**Tier 2 (High - Include if budget allows):**
- Report of Sale, Report of Foreclosure Sale
- Upset Bid (the filing document itself)
- Orders, Judgments
- Motions

**Tier 3 (Low - Fill remaining budget):**
- Affidavits, Certificates
- Correspondence, Notices
- OtherMiscellaneous

**Tier 4 (Exclude unless nothing else):**
- Cashier's checks, receipts
- `unknown_*.pdf` files (usually duplicates)

Within each tier, documents sorted by date (oldest first).

## Implementation

New function in `prompt_builder.py`:

```python
import hashlib

DOCUMENT_PRIORITY = {
    # Tier 1 - Always include
    'notice of hearing': 1,
    'deed of trust': 1,
    'notice of sale': 1,
    'notice of resale': 1,

    # Tier 2 - High priority
    'report of sale': 2,
    'report of foreclosure': 2,
    'upset bid': 2,
    'order': 2,
    'judgment': 2,
    'motion': 2,

    # Tier 3 - Medium priority
    'affidavit': 3,
    'certificate': 3,
    'correspondence': 3,
    'othermiscellaneous': 3,

    # Tier 4 - Low priority
    'check': 4,
    'receipt': 4,
    'unknown': 4,
}

MAX_DOCUMENT_CHARS = 600000  # ~150K tokens

def get_document_priority(document_name: str, case_number: str = None) -> int:
    """Get priority tier for a document (1=highest, 4=lowest)."""
    name_lower = document_name.lower()

    # Case filing document gets highest priority
    if case_number and case_number.lower() in name_lower:
        return 1

    # Match against known document types
    for keyword, priority in DOCUMENT_PRIORITY.items():
        if keyword in name_lower:
            return priority

    return 3  # Default to medium priority

def select_documents_for_prompt(documents: list, case_number: str = None,
                                 max_chars: int = MAX_DOCUMENT_CHARS) -> list:
    """
    Select and prioritize documents to fit within token budget.

    Args:
        documents: List of dicts with 'document_name', 'ocr_text', 'document_date'
        case_number: Case number for priority matching
        max_chars: Maximum total characters (~150K tokens)

    Returns:
        Filtered list of documents, prioritized and deduplicated
    """
    # 1. Deduplicate by content hash
    seen_hashes = set()
    unique_docs = []
    for doc in documents:
        if not doc.get('ocr_text'):
            continue
        content_hash = hashlib.md5(doc['ocr_text'].encode()).hexdigest()
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique_docs.append(doc)

    # 2. Assign priority tier to each document
    for doc in unique_docs:
        doc['_priority'] = get_document_priority(doc['document_name'], case_number)

    # 3. Sort by priority (ascending), then by date (oldest first)
    unique_docs.sort(key=lambda d: (d['_priority'], d.get('document_date') or ''))

    # 4. Select documents until budget exhausted
    selected = []
    total_chars = 0
    for doc in unique_docs:
        doc_chars = min(len(doc['ocr_text']), 15000)  # Existing per-doc truncation
        if total_chars + doc_chars <= max_chars:
            selected.append(doc)
            total_chars += doc_chars

    return selected
```

## Integration Point

In `build_analysis_prompt()`, replace direct document iteration with:

```python
# Before building prompt sections
filtered_docs = select_documents_for_prompt(documents, case_number)
logger.info(f"Selected {len(filtered_docs)}/{len(documents)} documents for analysis")

# Use filtered_docs instead of documents in the loop
```

## Testing

1. **Case 25SP000393-420** (309 docs)
   - Should select ~40-50 high-priority documents
   - Must extract deed Book 1294, Page 130

2. **Case 25SP000628-310** (324 docs)
   - Similar behavior, should succeed

3. **Normal case** (< 50 docs)
   - All documents included, no filtering

## Logging

- Total vs selected document count
- Documents excluded due to budget
- Content hashes for duplicate detection debugging

## Success Criteria

- Both failed cases complete successfully
- Deed book/page extracted correctly
- Cost remains ~$0.20-0.30 per case
