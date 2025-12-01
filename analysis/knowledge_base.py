"""NC Foreclosure Law Knowledge Base.

Tiered reference system for AI prompts:
- Tier 1: Core rules (always included, ~500 tokens)
- Tier 2: Lookup tables (always included, ~300 tokens)
- Tier 3: Full statute text (on-demand from file)
"""

from pathlib import Path

# Tier 1: Core Rules - Always included in prompts
CORE_RULES = """
NC FORECLOSURE UPSET BID RULES (NC GS Chapter 45, Article 2A):

UPSET BID PERIOD:
- Starts: When "Report of Sale" (GS 45-21.26) is filed with Clerk of Superior Court
- Duration: 10 calendar days from filing
- Extension: Each new upset bid restarts the 10-day clock
- Weekend/Holiday: If 10th day falls on weekend/holiday, extends to next business day

UPSET BID REQUIREMENTS (GS 45-21.27):
- Minimum increase: 5% above prior bid OR $750, whichever is GREATER
- Required deposit: 5% of bid amount (minimum $750)
- Must be filed with Clerk of Superior Court in person (no mail/online)
- Prior bidder released from obligations when upset bid filed

SALE FINALIZATION:
- If no upset bid within 10 days: highest bidder wins, sale becomes final
- After final: Trustee files Final Report (GS 45-21.33) within 30 days
- Possession: 10-day notice to occupants (GS 45-21.29), then sheriff removal

STATUS BLOCKERS (make upset bid period INVALID):
- Bankruptcy filing: Automatic stay under 11 USC 362 halts all foreclosure activity
- Military service: 90-day protection under SCRA and NC GS 45-21.23
- Sale vacated/cancelled by court order
- Appeal pending
- Relief from stay granted to creditor (resumes foreclosure)

BANKRUPTCY IMPACT:
- Chapter 7: Does not cure arrears, home typically lost
- Chapter 13: Can cure arrears over 3-5 year plan, keep home
- Automatic stay: Immediate upon filing, stops foreclosure
- Relief from stay: Creditor can petition, typically granted if no equity/plan
"""

# Tier 2: Lookup Tables - Compact structured reference
LIEN_PRIORITY = """
LIEN PRIORITY (highest to lowest):
1. LOCAL PROPERTY TAXES - Super-priority, survives ALL foreclosures (GS 105-356)
2. STATE TAX LIENS - First-in-time vs local taxes based on recording
3. FEDERAL IRS LIENS - Junior to local property tax; 120-day redemption right
4. FIRST MORTGAGE/DEED OF TRUST - Primary secured debt
5. JUNIOR LIENS - In order of recording date (second mortgage, HELOCs, judgments)
6. HOA LIENS - Lowest priority; extinguished by foreclosure of prior deed of trust

CRITICAL NOTES:
- Property tax liens CANNOT be extinguished by foreclosure
- IRS has 120-day right of redemption after foreclosure sale
- HOA liens in NC do NOT have super-priority (unlike some states)
"""

STATUS_BLOCKERS = [
    "bankruptcy_filed",
    "bankruptcy_chapter_7",
    "bankruptcy_chapter_13",
    "bankruptcy_chapter_11",
    "military_service",
    "scra_protection",
    "sale_vacated",
    "sale_cancelled",
    "appeal_pending",
    "motion_to_dismiss_granted",
    "stay_order",
    "continuance_granted",
]

KEY_EVENTS = {
    # Events that START the upset bid period
    "starts_upset_period": [
        "Report of Sale",
        "Report Of Foreclosure Sale",
        "Report Of Foreclosure Sale (Chapter 45)",
        "Trustee Report of Sale",
    ],
    # Events that EXTEND the upset bid period
    "extends_upset_period": [
        "Upset Bid Filed",
        "Notice of Upset Bid",
    ],
    # Events that may BLOCK/INVALIDATE the upset period
    "potential_blockers": [
        "Bankruptcy",
        "Notice of Bankruptcy",
        "Suggestion of Bankruptcy",
        "Motion to Dismiss",
        "Dismissed",
        "Voluntary Dismissal",
        "Order of Dismissal",
        "Stay",
        "Order Staying Proceedings",
        "Continuance",
        "Appeal",
        "Notice of Appeal",
        "Sale Vacated",
        "Order Vacating Sale",
    ],
    # Events that indicate case resolution
    "case_closed": [
        "Final Report",
        "Final Report of Sale",
        "Confirmation of Sale",
        "Deed Recorded",
        "Case Closed",
        "Satisfied",
    ],
}

RESEARCH_FLAGS = {
    "irs_lien": "Federal tax lien - IRS has 120-day redemption right",
    "state_tax_lien": "NC Department of Revenue lien",
    "multiple_mortgages": "More than one mortgage holder identified",
    "hoa_lien": "HOA/condo association lien (low priority but affects title)",
    "mechanics_lien": "Contractor/mechanic's lien under Chapter 44A",
    "judgment_lien": "Civil judgment docketed against property owner",
    "child_support_lien": "Child support arrears reduced to judgment",
    "outstanding_taxes": "Significant property tax arrears",
    "title_complexity": "Multiple transfers or unclear ownership history",
    "deficiency_risk": "Sale price likely below debt - deficiency judgment possible",
}


def get_core_rules() -> str:
    """Return Tier 1 core rules text for prompt inclusion."""
    return CORE_RULES.strip()


def get_lien_priority() -> str:
    """Return lien priority reference text."""
    return LIEN_PRIORITY.strip()


def get_status_blockers() -> list:
    """Return list of status blocker types."""
    return STATUS_BLOCKERS.copy()


def get_key_events() -> dict:
    """Return key events dictionary."""
    return KEY_EVENTS.copy()


def get_research_flags() -> dict:
    """Return research flag definitions."""
    return RESEARCH_FLAGS.copy()


def get_system_prompt() -> str:
    """Return complete system prompt with Tier 1 + Tier 2 content."""
    return f"""You are a foreclosure case analyst specializing in North Carolina properties.
Your job is to analyze case documents and verify upset bid status, calculate deadlines,
extract financial information, and flag items requiring further research.

{CORE_RULES}

{LIEN_PRIORITY}

CLASSIFICATION RULES (follow exactly):
The recommended_classification field MUST be one of these values based on these rules:

1. "upcoming" - Use when:
   - No "Report of Sale" or "Report of Foreclosure Sale" event/document exists
   - Case is pre-sale (foreclosure initiated but sale hasn't happened yet)
   - This is the DEFAULT for cases without a sale report

2. "upset_bid" - Use when:
   - A "Report of Sale" event/document EXISTS, AND
   - Current date is within 10 days of the sale report date (or extended deadline from upset bids)
   - Active upset bid period

3. "pending" - Use when:
   - Report of Sale exists, AND
   - The 10-day upset bid period has EXPIRED, AND
   - No blocking events (bankruptcy, dismissal)
   - Sale is final, awaiting deed transfer

4. "closed" - Use when:
   - Final Report filed, OR
   - Deed recorded, OR
   - Case explicitly marked closed/satisfied

5. "needs_review" - Use ONLY when:
   - There is a genuine CONFLICT between documents (contradictory dates/information)
   - Blocking event (bankruptcy, dismissal) exists that changes status
   - DO NOT use for "missing documents" - that's just "upcoming"

CRITICAL: Missing documents does NOT mean "needs_review". If there's no Report of Sale,
the classification is simply "upcoming" because the sale hasn't happened yet.

ANALYSIS GUIDELINES:
1. Cross-reference document dates with event data provided
2. Flag any discrepancies between documents and structured data
3. Extract specific dollar amounts, dates, and party names when found
4. Rate each document's usefulness for this analysis
5. Set is_valid_upset_bid=true ONLY if classification is "upset_bid"

Respond with valid JSON matching the schema provided in the user prompt.
"""


def get_full_statute(section: str) -> str:
    """
    Return full statute text for a specific section (Tier 3).

    Args:
        section: Statute section identifier (e.g., "45-21.27")

    Returns:
        Full statute text if available, otherwise empty string
    """
    statute_file = Path(__file__).parent / "nc_foreclosure_law.md"

    if not statute_file.exists():
        return ""

    content = statute_file.read_text()

    # Simple section extraction - look for markdown headers
    section_marker = f"## {section}" if not section.startswith("GS") else f"## GS {section}"
    alt_marker = f"## GS {section}"

    for marker in [section_marker, alt_marker, f"### {section}"]:
        if marker in content:
            start = content.find(marker)
            # Find next section header
            next_section = content.find("\n## ", start + len(marker))
            if next_section == -1:
                return content[start:].strip()
            return content[start:next_section].strip()

    return ""
