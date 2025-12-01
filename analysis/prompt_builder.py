"""Prompt builder for AI analysis.

Assembles prompts from case data, events, parties, and OCR text.
Implements smart batching for large document sets.
"""

import json
from typing import Optional
from sqlalchemy import text

from database.connection import get_session
from analysis.knowledge_base import get_system_prompt
from common.logger import setup_logger

logger = setup_logger(__name__)

# Token estimation: ~4 chars per token for English text
CHARS_PER_TOKEN = 4
MAX_TOKENS = 100000  # Leave headroom below Claude's 200K limit
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN

# JSON response schema for the AI
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_valid_upset_bid": {
            "type": "boolean",
            "description": "Whether this case is in a valid upset bid period"
        },
        "status_blockers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "date_found": {"type": "string", "format": "date"}
                }
            },
            "description": "List of issues that invalidate the upset bid period"
        },
        "recommended_classification": {
            "type": "string",
            "enum": ["upset_bid", "upcoming", "pending", "needs_review", "closed"],
            "description": "Recommended case classification"
        },
        "upset_deadline": {
            "type": "string",
            "format": "date",
            "description": "Calculated upset bid deadline (YYYY-MM-DD)"
        },
        "deadline_extended": {
            "type": "boolean",
            "description": "Whether deadline was extended by upset bids"
        },
        "extension_count": {
            "type": "integer",
            "description": "Number of upset bid extensions"
        },
        "current_bid_amount": {
            "type": "number",
            "description": "Current highest bid amount in dollars"
        },
        "estimated_total_liens": {
            "type": "number",
            "description": "Estimated total of all liens/debts on property"
        },
        "mortgage_info": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "holder": {"type": "string"},
                    "amount": {"type": "number"},
                    "rate": {"type": "string"},
                    "date": {"type": "string"}
                }
            },
            "description": "Mortgage details extracted from documents"
        },
        "tax_info": {
            "type": "object",
            "properties": {
                "outstanding": {"type": "number"},
                "year": {"type": "integer"},
                "county_assessed_value": {"type": "number"}
            },
            "description": "Property tax information"
        },
        "research_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]}
                }
            },
            "description": "Items requiring further research"
        },
        "document_evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "integer"},
                    "useful": {"type": "boolean"},
                    "doc_type": {"type": "string"},
                    "reason": {"type": "string"}
                }
            },
            "description": "Usefulness rating for each document"
        },
        "analysis_notes": {
            "type": "string",
            "description": "Free-form analysis, reasoning, and observations"
        },
        "confidence_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence in the analysis (0.0 to 1.0)"
        },
        "discrepancies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "expected": {"type": "string"},
                    "found": {"type": "string"}
                }
            },
            "description": "Discrepancies between documents and event data"
        }
    },
    "required": [
        "is_valid_upset_bid",
        "status_blockers",
        "recommended_classification",
        "research_flags",
        "document_evaluations",
        "analysis_notes",
        "confidence_score"
    ]
}


def get_case_info(case_id: int) -> dict:
    """Fetch case information from database."""
    with get_session() as session:
        result = session.execute(
            text("""
                SELECT id, case_number, county_name, file_date, case_type, case_status,
                       style, property_address, current_bid_amount, next_bid_deadline,
                       sale_date, classification
                FROM cases WHERE id = :case_id
            """),
            {"case_id": case_id}
        )
        row = result.fetchone()
        if not row:
            return {}

        return {
            "id": row[0],
            "case_number": row[1],
            "county": row[2],
            "file_date": str(row[3]) if row[3] else None,
            "case_type": row[4],
            "case_status": row[5],
            "style": row[6],
            "property_address": row[7],
            "current_bid_amount": float(row[8]) if row[8] else None,
            "next_bid_deadline": str(row[9]) if row[9] else None,
            "sale_date": str(row[10]) if row[10] else None,
            "classification": row[11],
        }


def get_case_events(case_id: int) -> list:
    """Fetch all events for a case."""
    with get_session() as session:
        result = session.execute(
            text("""
                SELECT event_date, event_type, filed_by, filed_against, hearing_date
                FROM case_events
                WHERE case_id = :case_id
                ORDER BY event_date DESC
            """),
            {"case_id": case_id}
        )
        events = []
        for row in result:
            events.append({
                "date": str(row[0]) if row[0] else None,
                "type": row[1],
                "filed_by": row[2],
                "filed_against": row[3],
                "hearing_date": str(row[4]) if row[4] else None,
            })
        return events


def get_case_parties(case_id: int) -> list:
    """Fetch all parties for a case."""
    with get_session() as session:
        result = session.execute(
            text("""
                SELECT party_type, party_name
                FROM parties
                WHERE case_id = :case_id
            """),
            {"case_id": case_id}
        )
        return [{"type": row[0], "name": row[1]} for row in result]


def get_case_documents(case_id: int, skip_patterns: list = None) -> list:
    """
    Fetch documents with OCR text for a case.

    Args:
        case_id: Case database ID
        skip_patterns: List of document name patterns to skip

    Returns:
        List of document dicts with id, name, date, ocr_text
    """
    skip_patterns = skip_patterns or []

    with get_session() as session:
        result = session.execute(
            text("""
                SELECT id, document_name, document_date, ocr_text
                FROM documents
                WHERE case_id = :case_id
                  AND ocr_text IS NOT NULL
                  AND ocr_text != ''
                ORDER BY document_date DESC NULLS LAST
            """),
            {"case_id": case_id}
        )

        documents = []
        for row in result:
            doc_name = row[1] or ""

            # Check skip patterns
            skip = False
            for pattern in skip_patterns:
                if pattern.lower() in doc_name.lower():
                    skip = True
                    break

            if not skip:
                documents.append({
                    "id": row[0],
                    "name": doc_name,
                    "date": str(row[2]) if row[2] else "Unknown",
                    "ocr_text": row[3] or "",
                })

        return documents


def batch_documents(documents: list, max_chars: int = MAX_CHARS) -> list:
    """
    Batch documents to fit within token limits.

    Args:
        documents: List of document dicts
        max_chars: Maximum characters per batch

    Returns:
        List of batches, each batch is a list of documents
    """
    batches = []
    current_batch = []
    current_chars = 0

    for doc in documents:
        doc_chars = len(doc.get("ocr_text", "")) + 200  # Add overhead for header

        if current_chars + doc_chars > max_chars and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0

        current_batch.append(doc)
        current_chars += doc_chars

    if current_batch:
        batches.append(current_batch)

    return batches


def format_documents_for_prompt(documents: list) -> str:
    """Format documents into prompt-ready text."""
    if not documents:
        return "No documents with OCR text available."

    sections = []
    for doc in documents:
        header = f"=== DOCUMENT: {doc['name']} (filed {doc['date']}) [ID: {doc['id']}] ==="
        sections.append(f"{header}\n{doc['ocr_text']}\n")

    return "\n".join(sections)


def build_prompt(case_id: int, skip_patterns: list = None) -> tuple:
    """
    Build complete prompt for a case.

    Args:
        case_id: Case database ID
        skip_patterns: Document patterns to skip

    Returns:
        tuple: (system_prompt, user_prompt, document_count)
    """
    # Gather data
    case_info = get_case_info(case_id)
    if not case_info:
        raise ValueError(f"Case {case_id} not found")

    events = get_case_events(case_id)
    parties = get_case_parties(case_id)
    documents = get_case_documents(case_id, skip_patterns)

    # Check if batching is needed
    total_chars = sum(len(d.get("ocr_text", "")) for d in documents)
    if total_chars > MAX_CHARS:
        logger.warning(f"Case {case_id} has {total_chars} chars, batching required")
        batches = batch_documents(documents)
        # For now, use first batch - future: implement multi-call merging
        documents = batches[0] if batches else []
        logger.info(f"Using first batch with {len(documents)} documents")

    # Build system prompt
    system_prompt = get_system_prompt()

    # Build user prompt
    user_prompt = f"""Analyze this foreclosure case:

=== CASE INFO ===
Case Number: {case_info.get('case_number', 'Unknown')}
County: {case_info.get('county', 'Unknown')}
File Date: {case_info.get('file_date', 'Unknown')}
Case Type: {case_info.get('case_type', 'Unknown')}
Case Status: {case_info.get('case_status', 'Unknown')}
Style: {case_info.get('style', 'Unknown')}
Current Classification: {case_info.get('classification', 'Unknown')}
Property Address: {case_info.get('property_address', 'Unknown')}
Current Bid Amount: {case_info.get('current_bid_amount', 'Unknown')}
Sale Date (if known): {case_info.get('sale_date', 'Unknown')}

=== PARTIES ===
{json.dumps(parties, indent=2) if parties else 'No parties recorded'}

=== EVENTS (from court system - use for validation) ===
{json.dumps(events, indent=2) if events else 'No events recorded'}

=== DOCUMENTS ({len(documents)} documents with OCR text) ===
{format_documents_for_prompt(documents)}

=== YOUR TASKS ===
1. Verify this case is in a valid upset bid period (check for status blockers)
2. Calculate the current upset bid deadline based on Report of Sale date and any extensions
3. Extract financial information (liens, mortgages, taxes) from the documents
4. Flag items requiring further research (IRS liens, title issues, etc.)
5. Rate each document's usefulness for this analysis
6. Note any discrepancies between documents and the event data above

Return your analysis as JSON matching this schema:
{json.dumps(RESPONSE_SCHEMA, indent=2)}

IMPORTANT:
- Dates should be in YYYY-MM-DD format
- Dollar amounts should be numbers without currency symbols
- Be conservative: if uncertain, set is_valid_upset_bid to false and explain in analysis_notes
- Flag any discrepancies between document dates and event dates
"""

    return system_prompt, user_prompt, len(documents)


def estimate_tokens(system_prompt: str, user_prompt: str) -> int:
    """Estimate token count for a prompt."""
    total_chars = len(system_prompt) + len(user_prompt)
    return total_chars // CHARS_PER_TOKEN
