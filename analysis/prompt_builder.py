# analysis/prompt_builder.py
"""Build Claude prompts for case analysis."""

import hashlib
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Document priority tiers for filtering
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

# Key NC foreclosure statutes for reference
NC_FORECLOSURE_STATUTES = """
**Key NC Foreclosure Statutes:**
- G.S. 45-21.16: Power of sale foreclosure requirements
- G.S. 45-21.17: Notice of hearing requirements
- G.S. 45-21.21: Posting and publication requirements
- G.S. 45-21.27: Upset bid period (10 days, extends if falls on weekend/holiday)
- G.S. 45-21.29: Confirmation of sale
- G.S. 45-21.31: Deficiency judgment provisions
- G.S. 45-21.33: Trustee's deed requirements
"""


def build_analysis_prompt(
    case_number: str,
    county: str,
    documents: List[Dict[str, Any]],
    current_db_values: Dict[str, Any],
    events: List[Dict[str, Any]] = None
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
        events: List of dicts with 'event_date', 'event_type', 'description'
            These are structured events from the court portal with accurate bid amounts

    Returns:
        The complete prompt string for Claude
    """
    # Select documents using smart filtering
    filtered_docs = select_documents_for_prompt(documents, case_number)
    logger.info(f"Selected {len(filtered_docs)}/{len(documents)} documents for analysis (case {case_number})")

    # Build document section
    doc_sections = []
    for i, doc in enumerate(filtered_docs, 1):
        doc_sections.append(f"""
--- DOCUMENT {i}: {doc['document_name']} ---
{doc['ocr_text'][:15000]}
--- END DOCUMENT {i} ---
""")

    documents_text = "\n".join(doc_sections)

    # Build events section (structured data from court portal - more reliable than OCR)
    events_text = ""
    if events:
        event_lines = []
        for event in events:
            date_str = event.get('event_date') or 'Unknown date'
            event_type = event.get('event_type') or 'Unknown type'
            desc = event.get('description') or ''
            event_lines.append(f"- [{date_str}] {event_type}: {desc}")
        events_text = "\n".join(event_lines)

    # Build red flags reference
    red_flags_reference = []
    for category, flags in RED_FLAG_CATEGORIES.items():
        red_flags_reference.append(f"**{category.title()}:** {', '.join(flags)}")
    red_flags_text = "\n".join(red_flags_reference)

    prompt = f"""You are an expert analyst reviewing a North Carolina foreclosure case. Generate a comprehensive legal analysis from the court documents and events provided.

## CASE INFORMATION
- Case Number: {case_number}
- County: {county}

## NC FORECLOSURE LEGAL FRAMEWORK
{NC_FORECLOSURE_STATUTES}

**NC Upset Bid Process (G.S. 45-21.27):**
- After a foreclosure sale, there is a 10-day upset bid period
- Anyone can submit a higher bid (minimum 5% increase) to purchase the property
- Each upset bid restarts the 10-day period
- If the 10th day falls on a weekend or court holiday, the deadline extends to the next business day
- Documents titled "Report of Upset Bid" indicate a new, higher bid was placed

## CURRENT DATABASE VALUES (for comparison)
- Property Address: {current_db_values.get('property_address', 'Not recorded')}
- Current Bid Amount: ${current_db_values.get('current_bid_amount', 'Not recorded')}
- Minimum Next Bid: ${current_db_values.get('minimum_next_bid', 'Not recorded')}
- Defendant Names: {', '.join(current_db_values.get('defendant_names', [])) or 'Not recorded'}

## DOCUMENTS TO ANALYZE
{documents_text}

## CASE EVENTS (from court portal - MOST RELIABLE for bid amounts)
{events_text if events_text else "No events with bid information available."}

**IMPORTANT:** Event descriptions like "Bid Amount $460,000.00" from "Upset Bid Filed" events are MORE RELIABLE than OCR'd document text, especially for handwritten amounts. Always prefer bid amounts from events when available.

## ANALYSIS INSTRUCTIONS

Generate a comprehensive JSON analysis with the following structure. Write in clear, professional prose for narrative sections.

```json
{{
  "comprehensive_analysis": {{
    "executive_summary": "<A single paragraph (4-6 sentences) providing a complete overview of this foreclosure case. Include: who the parties are, the property involved, the nature of the default, key events that occurred, current status, and outcome or expected resolution. This should give a reader complete context without reading further.>",

    "chronological_timeline": [
      {{
        "date": "<YYYY-MM-DD or approximate>",
        "event": "<What happened>",
        "significance": "<Why this matters to the case - only include if the event advances the foreclosure narrative>",
        "source": "<Document name or 'Portal Event'>"
      }}
    ],

    "parties_analysis": {{
      "plaintiff": {{
        "identity": "<Name and role (lender, servicer, trustee, etc.)>",
        "actions_taken": ["<List of significant actions/filings by plaintiff>"],
        "strategy_assessment": "<INFERRED: Analysis of plaintiff's approach, timing, and effectiveness. Clearly label this as analytical inference.>"
      }},
      "defendant": {{
        "identity": "<Name(s) and relationship to property (owner, borrower, etc.)>",
        "actions_taken": ["<List of responses, filings, or lack thereof>"],
        "strategy_assessment": "<INFERRED: Analysis of defendant's response or lack thereof, any defenses raised, effectiveness. Clearly label this as analytical inference.>"
      }},
      "other_parties": [
        {{
          "name": "<Party name>",
          "role": "<Role in case (junior lienholder, tenant, etc.)>",
          "relevance": "<How they affect the case>"
        }}
      ]
    }},

    "legal_procedural_analysis": {{
      "key_legal_issues": [
        {{
          "issue": "<Legal issue or question>",
          "resolution": "<How it was resolved or current status>",
          "applicable_statute": "<NC G.S. citation if applicable>"
        }}
      ],
      "procedural_compliance": {{
        "notice_requirements": "<Assessment of whether proper notices were given per G.S. 45-21.16/17>",
        "posting_publication": "<Assessment of posting/publication compliance per G.S. 45-21.21>",
        "sale_procedure": "<Assessment of sale procedure compliance>",
        "irregularities_noted": ["<Any procedural issues or irregularities found>"]
      }},
      "rulings_and_orders": [
        {{
          "date": "<Date of ruling>",
          "ruling": "<What was ordered>",
          "impact": "<Effect on case progression>"
        }}
      ]
    }},

    "conclusion_and_takeaways": {{
      "case_outcome": "<Current status or final resolution of the case>",
      "key_takeaways": [
        "<Most important point 1>",
        "<Most important point 2>",
        "<Most important point 3>"
      ],
      "investment_considerations": "<For a potential upset bidder: key risks, title concerns, or opportunities identified>"
    }}
  }},

  "financials": {{
    "mortgage_amount": <number or null - the original loan amount being foreclosed>,
    "lender": "<lender/servicer name or null>",
    "default_amount": <number or null - the amount needed to cure the default, NOT the total payoff>,
    "total_debt": <number or null - total amount owed including principal, interest, fees>,
    "liens": [
      {{"type": "<mortgage/tax/hoa/judgment/other>", "holder": "<name>", "amount": <number or null>, "priority": "<senior/junior/unknown>", "notes": "<any details>"}}
    ],
    "gaps": ["<list of financial information NOT found in documents>"]
  }},

  "red_flags": [
    {{"category": "<procedural|financial|property>", "description": "<specific issue found>", "severity": "<high|medium|low>", "source_document": "<document name>", "investment_impact": "<how this affects a potential bidder>"}}
  ],

  "confirmations": {{
    "property_address": "<address extracted from documents>",
    "current_bid_amount": <HIGHEST/MOST RECENT bid amount found - prefer event data over OCR>,
    "minimum_next_bid": <minimum next bid from MOST RECENT bid document>,
    "defendant_name": "<primary defendant name>"
  }},

  "deed_book": "<Deed Book number for the property's deed of trust - NOT Book of Maps or Plat Book>",
  "deed_page": "<Deed Page number corresponding to the Deed Book above>",

  "document_contributions": [
    {{"document_name": "<name>", "contributed_to": ["<sections this document informed>"], "key_extractions": ["<brief notes on what was extracted>"]}}
  ]
}}
```

## TIMELINE GUIDELINES
- Include only events that advance the foreclosure narrative (filing, service, hearings, sale, bids)
- EXCLUDE mundane procedural events like routine filings, administrative entries, or duplicate notices
- Combine portal events with significant dates extracted from documents
- Order chronologically

## FINANCIAL EXTRACTION GUIDELINES
- **default_amount**: The amount needed to CURE the default (reinstate the loan), NOT the total payoff
- **total_debt**: The full amount owed (principal + interest + fees + costs)
- These are different numbers - a borrower can cure default for less than total payoff
- If you see "Amount Required to Cure Default" vs "Total Payoff" - use the former for default_amount

## RED FLAGS TO WATCH FOR
{red_flags_text}

## DEED BOOK vs BOOK OF MAPS/PLAT BOOK
- **Deed Book**: Records property ownership transfers and deeds of trust (mortgages). This is what we need.
- **Book of Maps** (Wake County) / **Plat Book** (other counties): Records subdivision plat maps showing lot boundaries. Do NOT extract these.
- Example Deed reference: "recorded in Deed Book 15704, Page 1495" - EXTRACT THIS
- Example Plat reference: "as shown on map recorded in Book of Maps 2007, Page 1270" - IGNORE THIS
- Look for the deed of trust that secures the loan being foreclosed.

## IMPORTANT NOTES
1. Write narrative sections in clear, professional prose - not bullet points
2. For INFERRED analysis, explicitly label it as inference vs. documented fact
3. Cite specific NC statutes when relevant to legal issues
4. For confirmations, prefer event data (bid amounts) over OCR-extracted values
5. If a value cannot be determined, use null (not a string "null")
6. For amounts, use numbers without currency symbols or commas

Respond ONLY with the JSON object, no additional text."""

    return prompt


def estimate_token_count(text: str) -> int:
    """Rough estimate of token count (4 chars per token average)."""
    return len(text) // 4
