# analysis/prompt_builder.py
"""Build Claude prompts for case analysis."""

from typing import List, Dict, Any

# Red flag categories from design doc
RED_FLAG_CATEGORIES = {
    'procedural': [
        'Bankruptcy filings',
        'Multiple postponements or continuances',
        'Contested foreclosure (defendant fighting it)',
        'Missing required notices or documents'
    ],
    'financial': [
        'Unusually low bid (possible deficiency)',
        'Multiple liens mentioned',
        'IRS or federal tax liens',
        'HOA super-lien priority issues'
    ],
    'property': [
        'Tenant-occupied property mentioned',
        'Property condition issues noted',
        'Title defects mentioned',
        'Multiple defendants (complex ownership)'
    ]
}


def build_analysis_prompt(
    case_number: str,
    county: str,
    documents: List[Dict[str, Any]],
    current_db_values: Dict[str, Any]
) -> str:
    """
    Build the analysis prompt for Claude.

    Args:
        case_number: The case number (e.g., "25SP001234-910")
        county: County name (e.g., "Wake")
        documents: List of dicts with 'document_name' and 'ocr_text'
        current_db_values: Dict with current database values for comparison
            - property_address
            - current_bid_amount
            - minimum_next_bid
            - defendant_names (list from parties table)

    Returns:
        The complete prompt string for Claude
    """
    # Build document section
    doc_sections = []
    for i, doc in enumerate(documents, 1):
        doc_sections.append(f"""
--- DOCUMENT {i}: {doc['document_name']} ---
{doc['ocr_text'][:15000]}
--- END DOCUMENT {i} ---
""")

    documents_text = "\n".join(doc_sections)

    # Build red flags reference
    red_flags_reference = []
    for category, flags in RED_FLAG_CATEGORIES.items():
        red_flags_reference.append(f"**{category.title()}:** {', '.join(flags)}")
    red_flags_text = "\n".join(red_flags_reference)

    prompt = f"""You are analyzing a North Carolina foreclosure case. Extract key information from the court documents provided.

## CASE INFORMATION
- Case Number: {case_number}
- County: {county}

## CURRENT DATABASE VALUES (for comparison)
- Property Address: {current_db_values.get('property_address', 'Not recorded')}
- Current Bid Amount: ${current_db_values.get('current_bid_amount', 'Not recorded')}
- Minimum Next Bid: ${current_db_values.get('minimum_next_bid', 'Not recorded')}
- Defendant Names: {', '.join(current_db_values.get('defendant_names', [])) or 'Not recorded'}

## DOCUMENTS TO ANALYZE
{documents_text}

## ANALYSIS INSTRUCTIONS

Analyze all documents and provide a JSON response with the following structure:

```json
{{
  "summary": "2-3 sentence plain-language summary of this foreclosure case",

  "financials": {{
    "mortgage_amount": <number or null>,
    "lender": "<lender name or null>",
    "default_amount": <number or null>,
    "liens": [
      {{"type": "<mortgage/tax/hoa/judgment/other>", "holder": "<name>", "amount": <number or null>, "notes": "<any details>"}}
    ],
    "gaps": ["<list of financial information NOT found in documents>"]
  }},

  "red_flags": [
    {{"category": "<procedural|financial|property>", "description": "<specific issue found>", "severity": "<high|medium|low>", "source_document": "<document name>"}}
  ],

  "confirmations": {{
    "property_address": "<address extracted from documents>",
    "current_bid_amount": <number extracted>,
    "minimum_next_bid": <number extracted>,
    "defendant_name": "<primary defendant name>"
  }},

  "deed_book": "<deed book number if found, or null>",
  "deed_page": "<deed page number if found, or null>",

  "document_contributions": [
    {{"document_name": "<name>", "contributed_to": ["<summary|financials|red_flags|confirmations|deed_info>"], "key_extractions": ["<brief notes on what was extracted>"]}}
  ]
}}
```

## RED FLAGS TO WATCH FOR
{red_flags_text}

## IMPORTANT NOTES
1. For financials.gaps, explicitly list what you could NOT find (e.g., "No second mortgage information", "Tax lien status unknown")
2. For red_flags, only include issues you actually found evidence of in the documents
3. For confirmations, extract the values exactly as they appear in documents
4. For document_contributions, track which documents provided which information
5. If a value cannot be determined, use null (not a string "null")
6. For amounts, use numbers without currency symbols or commas

Respond ONLY with the JSON object, no additional text."""

    return prompt


def estimate_token_count(text: str) -> int:
    """Rough estimate of token count (4 chars per token average)."""
    return len(text) // 4
