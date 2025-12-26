# analysis/analyzer.py
"""Main orchestrator for AI case analysis."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

import anthropic

from common.config import Config
from common.logger import setup_logger
from database.connection import get_session
from database.models import Case, CaseAnalysis, CaseEvent, Document, Party
from analysis.prompt_builder import build_analysis_prompt

logger = setup_logger(__name__)

# Model configuration
MODEL_NAME = "claude-sonnet-4-20250514"
# Pricing: $3 per million input tokens, $15 per million output tokens
INPUT_COST_PER_MILLION = 3.0
OUTPUT_COST_PER_MILLION = 15.0


def analyze_case(case_id: int) -> Dict[str, Any]:
    """
    Run AI analysis on a case.

    Args:
        case_id: The case ID to analyze

    Returns:
        Dict with analysis results or error info
    """
    logger.info(f"Starting AI analysis for case_id={case_id}")

    with get_session() as session:
        # Get or create analysis record
        analysis = session.query(CaseAnalysis).filter_by(case_id=case_id).first()
        if not analysis:
            logger.error(f"No analysis record found for case_id={case_id}")
            return {'error': 'No analysis record found'}

        # Mark as processing
        analysis.status = 'processing'
        session.commit()

        try:
            # Fetch case and related data
            case = session.query(Case).filter_by(id=case_id).first()
            if not case:
                raise ValueError(f"Case {case_id} not found")

            # Fetch documents with OCR text
            documents = session.query(Document).filter(
                Document.case_id == case_id,
                Document.ocr_text.isnot(None),
                Document.ocr_text != ''
            ).all()

            if not documents:
                raise ValueError(f"No documents with OCR text for case {case_id}")

            # Fetch defendant names from parties table
            defendants = session.query(Party).filter(
                Party.case_id == case_id,
                Party.party_type.ilike('%defendant%')
            ).all()
            defendant_names = [d.party_name for d in defendants if d.party_name]

            # Build current DB values for comparison
            current_db_values = {
                'property_address': case.property_address,
                'current_bid_amount': float(case.current_bid_amount) if case.current_bid_amount else None,
                'minimum_next_bid': float(case.minimum_next_bid) if case.minimum_next_bid else None,
                'defendant_names': defendant_names
            }

            # Prepare document data - INCLUDING document_id for contribution tracking
            doc_data = [
                {
                    'document_id': doc.id,
                    'document_name': doc.document_name,
                    'ocr_text': doc.ocr_text
                }
                for doc in documents
            ]

            # Fetch case events with descriptions (structured data from portal)
            events = session.query(CaseEvent).filter(
                CaseEvent.case_id == case_id,
                CaseEvent.event_description.isnot(None),
                CaseEvent.event_description != ''
            ).order_by(CaseEvent.event_date.desc().nullslast()).all()

            event_data = [
                {
                    'event_date': str(event.event_date) if event.event_date else None,
                    'event_type': event.event_type,
                    'description': event.event_description
                }
                for event in events
                if event.event_type  # Only include events with types
            ]

            # Build prompt
            prompt = build_analysis_prompt(
                case_number=case.case_number,
                county=case.county_code,
                documents=doc_data,
                current_db_values=current_db_values,
                events=event_data
            )

            # Call Claude API
            result = _call_claude_api(prompt)

            if 'error' in result:
                raise ValueError(result['error'])

            # Parse response
            parsed = _parse_analysis_response(result['content'])

            # C2: Check for parse errors
            if 'parse_error' in parsed:
                raise ValueError(f"Failed to parse AI response: {parsed['parse_error']}")

            # I1: Validate required fields - now expects comprehensive_analysis instead of summary
            required_keys = ['comprehensive_analysis', 'financials', 'confirmations']
            missing = [k for k in required_keys if k not in parsed]
            if missing:
                raise ValueError(f"AI response missing required fields: {missing}")

            # Validate comprehensive_analysis structure
            comp_analysis = parsed.get('comprehensive_analysis', {})
            required_sections = ['executive_summary', 'chronological_timeline', 'parties_analysis',
                               'legal_procedural_analysis', 'conclusion_and_takeaways']
            missing_sections = [s for s in required_sections if s not in comp_analysis]
            if missing_sections:
                logger.warning(f"Comprehensive analysis missing sections: {missing_sections}")

            # Generate discrepancies
            discrepancies = _generate_discrepancies(
                parsed.get('confirmations', {}),
                current_db_values
            )

            # Update analysis record
            # Store comprehensive analysis as JSONB
            analysis.comprehensive_analysis = parsed.get('comprehensive_analysis')
            # Legacy summary field - extract executive_summary for backward compatibility
            analysis.summary = parsed.get('comprehensive_analysis', {}).get('executive_summary')
            analysis.financials = parsed.get('financials')
            analysis.red_flags = parsed.get('red_flags', [])
            analysis.defendant_name = parsed.get('confirmations', {}).get('defendant_name')
            analysis.deed_book = parsed.get('deed_book')
            analysis.deed_page = parsed.get('deed_page')
            analysis.discrepancies = discrepancies
            analysis.document_contributions = parsed.get('document_contributions', [])
            analysis.model_used = MODEL_NAME
            analysis.input_tokens = result.get('input_tokens', 0)
            analysis.output_tokens = result.get('output_tokens', 0)
            analysis.cost_cents = _calculate_cost_cents(
                result.get('input_tokens', 0),
                result.get('output_tokens', 0)
            )
            analysis.status = 'completed'
            analysis.completed_at = datetime.now()
            analysis.error_message = None

            # Trigger deed enrichment if book/page extracted
            if analysis.deed_book and analysis.deed_page:
                try:
                    from enrichments.deed import enrich_deed
                    deed_result = enrich_deed(case_id, analysis.deed_book, analysis.deed_page)
                    if deed_result.get('success'):
                        logger.info(f"Deed URL generated for case_id={case_id}")
                    else:
                        logger.warning(f"Deed enrichment failed for case_id={case_id}: {deed_result.get('error')}")
                except Exception as e:
                    logger.error(f"Deed enrichment error for case_id={case_id}: {e}")

            session.commit()

            logger.info(f"Completed AI analysis for case_id={case_id}, cost={analysis.cost_cents} cents")

            return {
                'status': 'completed',
                'case_id': case_id,
                'cost_cents': analysis.cost_cents,
                'discrepancies_found': len(discrepancies)
            }

        except Exception as e:
            logger.error(f"AI analysis failed for case_id={case_id}: {e}")
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.completed_at = datetime.now()
            session.commit()
            return {'error': str(e), 'case_id': case_id}


def _call_claude_api(prompt: str) -> Dict[str, Any]:
    """Call Claude API and return response."""
    try:
        client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=8192,  # Increased for comprehensive 5-section analysis
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return {
            'content': response.content[0].text,
            'input_tokens': response.usage.input_tokens,
            'output_tokens': response.usage.output_tokens
        }

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return {'error': str(e)}


def _parse_analysis_response(content: str) -> Dict[str, Any]:
    """Parse JSON response from Claude."""
    # Try to extract JSON from response
    content = content.strip()

    # Remove markdown code blocks if present
    if content.startswith('```'):
        lines = content.split('\n')
        # Remove first and last lines (```json and ```)
        content = '\n'.join(lines[1:-1])

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response as JSON: {e}")
        logger.debug(f"Response content: {content[:500]}")
        return {'parse_error': str(e)}


def _generate_discrepancies(
    confirmations: Dict[str, Any],
    db_values: Dict[str, Any]
) -> list:
    """Compare AI confirmations against DB values and generate discrepancies."""
    discrepancies = []

    # I2: Log missing confirmation fields
    for field in ['property_address', 'current_bid_amount', 'minimum_next_bid', 'defendant_name']:
        if field not in confirmations or confirmations[field] is None:
            logger.warning(f"AI analysis did not extract {field}")

    # Compare property address
    ai_address = confirmations.get('property_address')
    db_address = db_values.get('property_address')
    if ai_address and db_address and _normalize_string(ai_address) != _normalize_string(db_address):
        discrepancies.append({
            'field': 'property_address',
            'db_value': db_address,
            'ai_value': ai_address,
            'status': 'pending',
            'resolved_at': None,
            'resolved_by': None
        })

    # Compare current bid (I3: Use Decimal for float comparison)
    # NOTE: If DB has a HIGHER value, don't flag as discrepancy - this means an upset bid
    # occurred that we already captured. Upset bid documents often have handwritten amounts
    # that can't be OCR'd, so AI may only see the original sale amount.
    ai_bid = confirmations.get('current_bid_amount')
    db_bid = db_values.get('current_bid_amount')
    if ai_bid and db_bid:
        ai_bid_dec = Decimal(str(ai_bid))
        db_bid_dec = Decimal(str(db_bid))
        # Only flag if values differ AND AI value is higher (potential DB error)
        # If DB is higher, that's likely correct from an upset bid we captured
        if abs(ai_bid_dec - db_bid_dec) > Decimal('0.01') and ai_bid_dec > db_bid_dec:
            discrepancies.append({
                'field': 'current_bid_amount',
                'db_value': str(db_bid),
                'ai_value': str(ai_bid),
                'status': 'pending',
                'resolved_at': None,
                'resolved_by': None
            })

    # Compare minimum next bid (I3: Use Decimal for float comparison)
    # Same logic: only flag if AI found higher value (DB lower might be outdated)
    ai_min = confirmations.get('minimum_next_bid')
    db_min = db_values.get('minimum_next_bid')
    if ai_min and db_min:
        ai_min_dec = Decimal(str(ai_min))
        db_min_dec = Decimal(str(db_min))
        if abs(ai_min_dec - db_min_dec) > Decimal('0.01') and ai_min_dec > db_min_dec:
            discrepancies.append({
                'field': 'minimum_next_bid',
                'db_value': str(db_min),
                'ai_value': str(ai_min),
                'status': 'pending',
                'resolved_at': None,
                'resolved_by': None
            })

    # Compare defendant name
    ai_defendant = confirmations.get('defendant_name')
    db_defendants = db_values.get('defendant_names', [])
    if ai_defendant and db_defendants:
        # Check if AI defendant matches any DB defendant
        ai_normalized = _normalize_string(ai_defendant)
        matches = any(_normalize_string(d) == ai_normalized for d in db_defendants)
        if not matches:
            discrepancies.append({
                'field': 'defendant_name',
                'db_value': ', '.join(db_defendants),
                'ai_value': ai_defendant,
                'status': 'pending',
                'resolved_at': None,
                'resolved_by': None
            })
    elif ai_defendant and not db_defendants:
        # AI found defendant but DB has none
        discrepancies.append({
            'field': 'defendant_name',
            'db_value': None,
            'ai_value': ai_defendant,
            'status': 'pending',
            'resolved_at': None,
            'resolved_by': None
        })

    return discrepancies


def _normalize_string(s: str) -> str:
    """Normalize string for comparison."""
    if not s:
        return ''
    return ' '.join(s.lower().split())


def _calculate_cost_cents(input_tokens: int, output_tokens: int) -> int:
    """Calculate cost in cents."""
    input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_MILLION
    output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION
    total_dollars = input_cost + output_cost
    return int(total_dollars * 100)  # Convert to cents
