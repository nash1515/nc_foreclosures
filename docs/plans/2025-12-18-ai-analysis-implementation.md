# AI Analysis Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build automated AI analysis of foreclosure cases when they transition to `upset_bid` status, extracting summaries, financials, red flags, and data confirmations.

**Architecture:** Database-backed queue triggers Claude Sonnet analysis. Results stored in `case_analyses` table. Frontend displays analysis in Case Detail page with discrepancy review workflow.

**Tech Stack:** Python/SQLAlchemy (backend), Anthropic API (Claude Sonnet), React/Ant Design (frontend), PostgreSQL with JSONB columns.

---

## Task 1: Database Migration

**Files:**
- Create: `migrations/add_case_analyses.sql`

**Step 1: Write the migration file**

```sql
-- migrations/add_case_analyses.sql
-- AI Analysis table for storing Claude analysis results

CREATE TABLE IF NOT EXISTS case_analyses (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id) ON DELETE CASCADE,

    -- Analysis outputs
    summary TEXT,
    financials JSONB,
    red_flags JSONB,
    defendant_name VARCHAR(255),
    deed_book VARCHAR(50),
    deed_page VARCHAR(50),

    -- Discrepancy tracking
    discrepancies JSONB,

    -- Document contribution tracking
    document_contributions JSONB,

    -- Metadata
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    model_used VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents INTEGER,
    requested_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_case_analyses_status ON case_analyses(status);
CREATE INDEX IF NOT EXISTS idx_case_analyses_case_id ON case_analyses(case_id);

COMMENT ON TABLE case_analyses IS 'AI analysis results for upset_bid cases';
COMMENT ON COLUMN case_analyses.financials IS 'JSON: {mortgage_amount, lender, liens[], taxes, judgments, gaps[]}';
COMMENT ON COLUMN case_analyses.red_flags IS 'JSON array: [{category, description, severity}]';
COMMENT ON COLUMN case_analyses.discrepancies IS 'JSON array: [{field, db_value, ai_value, status, resolved_at, resolved_by}]';
COMMENT ON COLUMN case_analyses.document_contributions IS 'JSON array: [{document_id, document_name, contributed_to[], key_extractions[]}]';
```

**Step 2: Run the migration**

Run: `PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f migrations/add_case_analyses.sql`

Expected: `CREATE TABLE` and `CREATE INDEX` messages (no errors)

**Step 3: Verify table exists**

Run: `PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d case_analyses"`

Expected: Table structure with all columns listed

**Step 4: Commit**

```bash
git add migrations/add_case_analyses.sql
git commit -m "feat: add case_analyses table for AI analysis results"
```

---

## Task 2: SQLAlchemy Model

**Files:**
- Modify: `database/models.py`
- Create: `analysis/__init__.py`
- Create: `analysis/models.py`

**Step 1: Add CaseAnalysis model to database/models.py**

Add after the existing model imports (around line 10):

```python
from sqlalchemy.dialects.postgresql import JSONB
```

Add after the last model class (after SchedulerConfig):

```python
class CaseAnalysis(Base):
    """AI analysis results for upset_bid cases."""
    __tablename__ = 'case_analyses'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, unique=True)

    # Analysis outputs
    summary = Column(Text)
    financials = Column(JSONB)
    red_flags = Column(JSONB)
    defendant_name = Column(String(255))
    deed_book = Column(String(50))
    deed_page = Column(String(50))

    # Discrepancy tracking
    discrepancies = Column(JSONB)

    # Document contribution tracking
    document_contributions = Column(JSONB)

    # Metadata
    status = Column(String(20), nullable=False, default='pending')
    model_used = Column(String(50))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cost_cents = Column(Integer)
    requested_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    completed_at = Column(TIMESTAMP)
    error_message = Column(Text)

    # Relationship
    case = relationship("Case", backref="analysis")

    def __repr__(self):
        return f"<CaseAnalysis(case_id={self.case_id}, status={self.status})>"
```

**Step 2: Create analysis module init**

```python
# analysis/__init__.py
"""AI Analysis module for foreclosure case analysis."""
```

**Step 3: Verify model loads without errors**

Run: `PYTHONPATH=$(pwd) python -c "from database.models import CaseAnalysis; print('CaseAnalysis model loaded')"`

Expected: `CaseAnalysis model loaded`

**Step 4: Commit**

```bash
git add database/models.py analysis/__init__.py
git commit -m "feat: add CaseAnalysis SQLAlchemy model"
```

---

## Task 3: Prompt Builder

**Files:**
- Create: `analysis/prompt_builder.py`

**Step 1: Create the prompt builder module**

```python
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
```

**Step 2: Verify module loads**

Run: `PYTHONPATH=$(pwd) python -c "from analysis.prompt_builder import build_analysis_prompt; print('Prompt builder loaded')"`

Expected: `Prompt builder loaded`

**Step 3: Commit**

```bash
git add analysis/prompt_builder.py
git commit -m "feat: add prompt builder for AI analysis"
```

---

## Task 4: Case Analyzer

**Files:**
- Create: `analysis/analyzer.py`

**Step 1: Create the analyzer module**

```python
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
from database.models import Case, CaseAnalysis, Document, Party
from analysis.prompt_builder import build_analysis_prompt, estimate_token_count

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

            # Prepare document data
            doc_data = [
                {'document_name': doc.document_name, 'ocr_text': doc.ocr_text}
                for doc in documents
            ]

            # Build prompt
            prompt = build_analysis_prompt(
                case_number=case.case_number,
                county=case.county_code,
                documents=doc_data,
                current_db_values=current_db_values
            )

            # Call Claude API
            result = _call_claude_api(prompt)

            if 'error' in result:
                raise ValueError(result['error'])

            # Parse response
            parsed = _parse_analysis_response(result['content'])

            # Generate discrepancies
            discrepancies = _generate_discrepancies(
                parsed.get('confirmations', {}),
                current_db_values
            )

            # Update analysis record
            analysis.summary = parsed.get('summary')
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
            max_tokens=4096,
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

    # Compare current bid
    ai_bid = confirmations.get('current_bid_amount')
    db_bid = db_values.get('current_bid_amount')
    if ai_bid and db_bid and float(ai_bid) != float(db_bid):
        discrepancies.append({
            'field': 'current_bid_amount',
            'db_value': str(db_bid),
            'ai_value': str(ai_bid),
            'status': 'pending',
            'resolved_at': None,
            'resolved_by': None
        })

    # Compare minimum next bid
    ai_min = confirmations.get('minimum_next_bid')
    db_min = db_values.get('minimum_next_bid')
    if ai_min and db_min and float(ai_min) != float(db_min):
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
```

**Step 2: Verify module loads**

Run: `PYTHONPATH=$(pwd) python -c "from analysis.analyzer import analyze_case; print('Analyzer loaded')"`

Expected: `Analyzer loaded`

**Step 3: Commit**

```bash
git add analysis/analyzer.py
git commit -m "feat: add case analyzer with Claude API integration"
```

---

## Task 5: Queue Processor

**Files:**
- Create: `analysis/queue_processor.py`

**Step 1: Create the queue processor module**

```python
# analysis/queue_processor.py
"""Process pending AI analysis queue."""

from typing import Dict, Any, List
from datetime import datetime

from common.logger import setup_logger
from database.connection import get_session
from database.models import CaseAnalysis
from analysis.analyzer import analyze_case

logger = setup_logger(__name__)


def process_analysis_queue(max_items: int = 10) -> Dict[str, Any]:
    """
    Process pending analyses from the queue.

    Args:
        max_items: Maximum number of analyses to process in one run

    Returns:
        Dict with processing results
    """
    logger.info("Starting analysis queue processing")

    results = {
        'processed': 0,
        'succeeded': 0,
        'failed': 0,
        'details': []
    }

    with get_session() as session:
        # Get pending analyses ordered by request time
        pending = session.query(CaseAnalysis).filter(
            CaseAnalysis.status == 'pending'
        ).order_by(
            CaseAnalysis.requested_at
        ).limit(max_items).all()

        if not pending:
            logger.info("No pending analyses found")
            return results

        logger.info(f"Found {len(pending)} pending analyses")

    # Process each analysis (outside session to avoid long transactions)
    for analysis in pending:
        case_id = analysis.case_id
        result = analyze_case(case_id)

        results['processed'] += 1
        if result.get('status') == 'completed':
            results['succeeded'] += 1
        else:
            results['failed'] += 1

        results['details'].append({
            'case_id': case_id,
            'status': result.get('status', 'failed'),
            'error': result.get('error'),
            'cost_cents': result.get('cost_cents', 0)
        })

    logger.info(f"Queue processing complete: {results['succeeded']}/{results['processed']} succeeded")
    return results


def enqueue_analysis(case_id: int) -> bool:
    """
    Add a case to the analysis queue.

    Args:
        case_id: The case ID to queue for analysis

    Returns:
        True if queued successfully, False if already queued
    """
    with get_session() as session:
        # Check if already queued
        existing = session.query(CaseAnalysis).filter_by(case_id=case_id).first()
        if existing:
            logger.debug(f"Case {case_id} already has analysis record (status={existing.status})")
            return False

        # Create new analysis record
        analysis = CaseAnalysis(
            case_id=case_id,
            status='pending',
            requested_at=datetime.now()
        )
        session.add(analysis)
        session.commit()

        logger.info(f"Queued case {case_id} for AI analysis")
        return True


def get_queue_status() -> Dict[str, Any]:
    """Get current queue status."""
    with get_session() as session:
        pending = session.query(CaseAnalysis).filter_by(status='pending').count()
        processing = session.query(CaseAnalysis).filter_by(status='processing').count()
        completed = session.query(CaseAnalysis).filter_by(status='completed').count()
        failed = session.query(CaseAnalysis).filter_by(status='failed').count()

        return {
            'pending': pending,
            'processing': processing,
            'completed': completed,
            'failed': failed,
            'total': pending + processing + completed + failed
        }
```

**Step 2: Verify module loads**

Run: `PYTHONPATH=$(pwd) python -c "from analysis.queue_processor import process_analysis_queue, enqueue_analysis; print('Queue processor loaded')"`

Expected: `Queue processor loaded`

**Step 3: Commit**

```bash
git add analysis/queue_processor.py
git commit -m "feat: add analysis queue processor"
```

---

## Task 6: Integration with Case Monitor

**Files:**
- Modify: `scraper/case_monitor.py`

**Step 1: Add import at top of file**

After existing imports, add:

```python
from analysis.queue_processor import enqueue_analysis
```

**Step 2: Add analysis trigger after classification change**

Find the section where `case.classification` is updated to `'upset_bid'`. After the classification is set and committed, add:

```python
# Queue for AI analysis when case transitions to upset_bid
if case.classification == 'upset_bid':
    try:
        enqueue_analysis(case.id)
    except Exception as e:
        logger.warning(f"Failed to queue analysis for case {case.id}: {e}")
```

**Step 3: Verify import works**

Run: `PYTHONPATH=$(pwd) python -c "from scraper.case_monitor import CaseMonitor; print('Case monitor loads with analysis integration')"`

Expected: `Case monitor loads with analysis integration`

**Step 4: Commit**

```bash
git add scraper/case_monitor.py
git commit -m "feat: trigger AI analysis when case becomes upset_bid"
```

---

## Task 7: Add Analysis Task to Daily Scrape

**Files:**
- Modify: `scraper/daily_scrape.py`

**Step 1: Add import at top of file**

After existing imports, add:

```python
from analysis.queue_processor import process_analysis_queue
```

**Step 2: Add Task 6 after self-diagnosis (Task 5)**

Find the section after Task 5 (self-diagnosis) and add:

```python
# Task 6: Process AI Analysis Queue
task_id = task_logger.start_task('ai_analysis_queue')
try:
    logger.info("Task 6: Processing AI analysis queue")
    analysis_result = process_analysis_queue(max_items=10)
    task_logger.complete_task(
        task_id,
        'success',
        items_checked=analysis_result['processed'],
        items_processed=analysis_result['succeeded']
    )
    logger.info(f"Task 6 complete: {analysis_result['succeeded']}/{analysis_result['processed']} analyses completed")
except Exception as e:
    logger.error(f"Task 6 failed: {e}")
    task_logger.complete_task(task_id, 'failed', error_message=str(e))
```

**Step 3: Verify daily scrape still loads**

Run: `PYTHONPATH=$(pwd) python -c "from scraper.daily_scrape import run_daily_tasks; print('Daily scrape loads with analysis task')"`

Expected: `Daily scrape loads with analysis task`

**Step 4: Commit**

```bash
git add scraper/daily_scrape.py
git commit -m "feat: add AI analysis queue processing to daily scrape"
```

---

## Task 8: API Endpoints

**Files:**
- Create: `web_app/api/analysis.py`
- Modify: `web_app/app.py`

**Step 1: Create analysis API routes**

```python
# web_app/api/analysis.py
"""API endpoints for AI analysis."""

from datetime import datetime
from flask import Blueprint, jsonify, request

from common.logger import setup_logger
from database.connection import get_session
from database.models import Case, CaseAnalysis, Party
from web_app.auth.middleware import require_auth

logger = setup_logger(__name__)

analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/cases')


@analysis_bp.route('/<int:case_id>/analysis', methods=['GET'])
@require_auth
def get_analysis(case_id):
    """Get analysis results for a case."""
    with get_session() as session:
        analysis = session.query(CaseAnalysis).filter_by(case_id=case_id).first()

        if not analysis:
            return jsonify({'status': 'not_found', 'message': 'No analysis for this case'}), 404

        return jsonify({
            'status': analysis.status,
            'summary': analysis.summary,
            'financials': analysis.financials,
            'red_flags': analysis.red_flags or [],
            'discrepancies': analysis.discrepancies or [],
            'defendant_name': analysis.defendant_name,
            'deed_book': analysis.deed_book,
            'deed_page': analysis.deed_page,
            'document_contributions': analysis.document_contributions or [],
            'model_used': analysis.model_used,
            'input_tokens': analysis.input_tokens,
            'output_tokens': analysis.output_tokens,
            'cost_cents': analysis.cost_cents,
            'requested_at': analysis.requested_at.isoformat() if analysis.requested_at else None,
            'completed_at': analysis.completed_at.isoformat() if analysis.completed_at else None,
            'error_message': analysis.error_message
        })


@analysis_bp.route('/<int:case_id>/analysis/discrepancies/<int:index>/resolve', methods=['POST'])
@require_auth
def resolve_discrepancy(case_id, index):
    """Resolve a discrepancy (accept or reject AI value)."""
    data = request.get_json()
    action = data.get('action')  # 'accept' or 'reject'

    if action not in ('accept', 'reject'):
        return jsonify({'error': 'action must be "accept" or "reject"'}), 400

    with get_session() as session:
        analysis = session.query(CaseAnalysis).filter_by(case_id=case_id).first()

        if not analysis:
            return jsonify({'error': 'No analysis for this case'}), 404

        discrepancies = analysis.discrepancies or []

        if index < 0 or index >= len(discrepancies):
            return jsonify({'error': 'Invalid discrepancy index'}), 400

        discrepancy = discrepancies[index]

        if discrepancy.get('status') != 'pending':
            return jsonify({'error': 'Discrepancy already resolved'}), 400

        # Update discrepancy status
        discrepancy['status'] = 'accepted' if action == 'accept' else 'rejected'
        discrepancy['resolved_at'] = datetime.now().isoformat()
        discrepancy['resolved_by'] = 'user'  # Could get actual user from session

        # If accepting, update the database field
        if action == 'accept':
            case = session.query(Case).filter_by(id=case_id).first()
            field = discrepancy['field']
            ai_value = discrepancy['ai_value']

            if field == 'property_address':
                case.property_address = ai_value
            elif field == 'current_bid_amount':
                case.current_bid_amount = float(ai_value)
            elif field == 'minimum_next_bid':
                case.minimum_next_bid = float(ai_value)
            elif field == 'defendant_name':
                # Add as new party if doesn't exist
                existing = session.query(Party).filter(
                    Party.case_id == case_id,
                    Party.party_name == ai_value
                ).first()
                if not existing:
                    new_party = Party(
                        case_id=case_id,
                        party_name=ai_value,
                        party_type='Defendant'
                    )
                    session.add(new_party)

            logger.info(f"Updated {field} for case {case_id} with AI value: {ai_value}")

        # Save updated discrepancies
        analysis.discrepancies = discrepancies
        session.commit()

        return jsonify({
            'success': True,
            'discrepancy': discrepancy
        })


@analysis_bp.route('/<int:case_id>/analysis/rerun', methods=['POST'])
@require_auth
def rerun_analysis(case_id):
    """Rerun analysis for a case (resets to pending)."""
    with get_session() as session:
        analysis = session.query(CaseAnalysis).filter_by(case_id=case_id).first()

        if not analysis:
            # Create new analysis record
            analysis = CaseAnalysis(case_id=case_id, status='pending')
            session.add(analysis)
        else:
            # Reset existing record
            analysis.status = 'pending'
            analysis.error_message = None
            analysis.requested_at = datetime.now()

        session.commit()

        return jsonify({'success': True, 'status': 'pending'})
```

**Step 2: Register blueprint in app.py**

In `web_app/app.py`, add import:

```python
from web_app.api.analysis import analysis_bp
```

And register blueprint (after other blueprint registrations):

```python
app.register_blueprint(analysis_bp)
```

**Step 3: Verify API loads**

Run: `PYTHONPATH=$(pwd) python -c "from web_app.api.analysis import analysis_bp; print('Analysis API loaded')"`

Expected: `Analysis API loaded`

**Step 4: Commit**

```bash
git add web_app/api/analysis.py web_app/app.py
git commit -m "feat: add API endpoints for AI analysis"
```

---

## Task 9: Frontend - API Client

**Files:**
- Create: `frontend/src/api/analysis.js`

**Step 1: Create analysis API client**

```javascript
// frontend/src/api/analysis.js
const API_BASE = import.meta.env.VITE_API_BASE || '';

export async function fetchAnalysis(caseId) {
  const response = await fetch(`${API_BASE}/api/cases/${caseId}/analysis`, {
    credentials: 'include'
  });

  if (response.status === 404) {
    return null; // No analysis yet
  }

  if (!response.ok) {
    throw new Error('Failed to fetch analysis');
  }

  return response.json();
}

export async function resolveDiscrepancy(caseId, index, action) {
  const response = await fetch(
    `${API_BASE}/api/cases/${caseId}/analysis/discrepancies/${index}/resolve`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    }
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to resolve discrepancy');
  }

  return response.json();
}

export async function rerunAnalysis(caseId) {
  const response = await fetch(
    `${API_BASE}/api/cases/${caseId}/analysis/rerun`,
    {
      method: 'POST',
      credentials: 'include'
    }
  );

  if (!response.ok) {
    throw new Error('Failed to rerun analysis');
  }

  return response.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/analysis.js
git commit -m "feat: add frontend API client for analysis"
```

---

## Task 10: Frontend - AI Analysis Section Component

**Files:**
- Create: `frontend/src/components/AIAnalysisSection.jsx`

**Step 1: Create the component**

```jsx
// frontend/src/components/AIAnalysisSection.jsx
import React, { useState, useEffect } from 'react';
import { Card, Typography, Tag, Table, Button, Space, Alert, Spin, Empty, Descriptions, List, message } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined,
  DollarOutlined,
  WarningOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import { fetchAnalysis, resolveDiscrepancy, rerunAnalysis } from '../api/analysis';

const { Title, Text, Paragraph } = Typography;

const SEVERITY_COLORS = {
  high: 'red',
  medium: 'orange',
  low: 'blue'
};

const CATEGORY_ICONS = {
  procedural: <FileTextOutlined />,
  financial: <DollarOutlined />,
  property: <WarningOutlined />
};

export default function AIAnalysisSection({ caseId }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(null);

  useEffect(() => {
    loadAnalysis();
  }, [caseId]);

  const loadAnalysis = async () => {
    setLoading(true);
    try {
      const data = await fetchAnalysis(caseId);
      setAnalysis(data);
    } catch (err) {
      message.error('Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (index, action) => {
    setResolving(index);
    try {
      await resolveDiscrepancy(caseId, index, action);
      message.success(action === 'accept' ? 'Value updated' : 'Kept current value');
      loadAnalysis();
    } catch (err) {
      message.error(err.message);
    } finally {
      setResolving(null);
    }
  };

  const handleRerun = async () => {
    try {
      await rerunAnalysis(caseId);
      message.success('Analysis queued for rerun');
      loadAnalysis();
    } catch (err) {
      message.error('Failed to rerun analysis');
    }
  };

  if (loading) {
    return <Card title="AI Analysis"><Spin /></Card>;
  }

  if (!analysis) {
    return (
      <Card title="AI Analysis">
        <Empty description="No AI analysis available for this case" />
      </Card>
    );
  }

  if (analysis.status === 'pending') {
    return (
      <Card title="AI Analysis">
        <Alert
          message="Analysis Pending"
          description="This case is queued for AI analysis. Check back soon."
          type="info"
          showIcon
        />
      </Card>
    );
  }

  if (analysis.status === 'processing') {
    return (
      <Card title="AI Analysis">
        <Alert
          message="Analysis In Progress"
          description="AI is currently analyzing this case..."
          type="info"
          showIcon
          icon={<Spin size="small" />}
        />
      </Card>
    );
  }

  if (analysis.status === 'failed') {
    return (
      <Card
        title="AI Analysis"
        extra={<Button icon={<ReloadOutlined />} onClick={handleRerun}>Retry</Button>}
      >
        <Alert
          message="Analysis Failed"
          description={analysis.error_message || 'Unknown error'}
          type="error"
          showIcon
        />
      </Card>
    );
  }

  // Completed analysis
  const pendingDiscrepancies = (analysis.discrepancies || []).filter(d => d.status === 'pending');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Summary Card */}
      <Card
        title="Case Summary"
        size="small"
        extra={
          <Space>
            <Text type="secondary">Cost: ${(analysis.cost_cents / 100).toFixed(2)}</Text>
            <Button icon={<ReloadOutlined />} size="small" onClick={handleRerun}>Rerun</Button>
          </Space>
        }
      >
        <Paragraph>{analysis.summary || 'No summary available'}</Paragraph>
      </Card>

      {/* Financials Card */}
      <Card title="Financial Analysis" size="small">
        {analysis.financials ? (
          <>
            <Descriptions column={2} size="small">
              {analysis.financials.mortgage_amount && (
                <Descriptions.Item label="Mortgage Amount">
                  ${analysis.financials.mortgage_amount.toLocaleString()}
                </Descriptions.Item>
              )}
              {analysis.financials.lender && (
                <Descriptions.Item label="Lender">
                  {analysis.financials.lender}
                </Descriptions.Item>
              )}
              {analysis.financials.default_amount && (
                <Descriptions.Item label="Default Amount">
                  ${analysis.financials.default_amount.toLocaleString()}
                </Descriptions.Item>
              )}
            </Descriptions>

            {analysis.financials.liens?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>Liens Found:</Text>
                <List
                  size="small"
                  dataSource={analysis.financials.liens}
                  renderItem={lien => (
                    <List.Item>
                      <Tag color="orange">{lien.type}</Tag>
                      {lien.holder}
                      {lien.amount && `: $${lien.amount.toLocaleString()}`}
                      {lien.notes && <Text type="secondary"> - {lien.notes}</Text>}
                    </List.Item>
                  )}
                />
              </div>
            )}

            {analysis.financials.gaps?.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text type="secondary">Information Not Found:</Text>
                <div style={{ marginTop: 4 }}>
                  {analysis.financials.gaps.map((gap, i) => (
                    <Tag key={i} color="default">{gap}</Tag>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : (
          <Text type="secondary">No financial information extracted</Text>
        )}
      </Card>

      {/* Red Flags Card */}
      <Card
        title={
          <Space>
            Red Flags
            {analysis.red_flags?.length > 0 && (
              <Tag color="red">{analysis.red_flags.length}</Tag>
            )}
          </Space>
        }
        size="small"
      >
        {analysis.red_flags?.length > 0 ? (
          <List
            size="small"
            dataSource={analysis.red_flags}
            renderItem={flag => (
              <List.Item>
                <Space>
                  {CATEGORY_ICONS[flag.category]}
                  <Tag color={SEVERITY_COLORS[flag.severity]}>{flag.severity}</Tag>
                  <Text>{flag.description}</Text>
                  {flag.source_document && (
                    <Text type="secondary">({flag.source_document})</Text>
                  )}
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Text type="success"><CheckCircleOutlined /> No red flags identified</Text>
        )}
      </Card>

      {/* Discrepancies Card */}
      {pendingDiscrepancies.length > 0 && (
        <Card
          title={
            <Space>
              <ExclamationCircleOutlined style={{ color: '#faad14' }} />
              Data Discrepancies
              <Tag color="orange">{pendingDiscrepancies.length} pending</Tag>
            </Space>
          }
          size="small"
        >
          <Table
            size="small"
            pagination={false}
            dataSource={analysis.discrepancies.map((d, i) => ({ ...d, index: i }))}
            columns={[
              {
                title: 'Field',
                dataIndex: 'field',
                key: 'field',
                render: field => field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
              },
              {
                title: 'Current Value',
                dataIndex: 'db_value',
                key: 'db_value',
                render: val => val || <Text type="secondary">Not set</Text>
              },
              {
                title: 'AI Found',
                dataIndex: 'ai_value',
                key: 'ai_value'
              },
              {
                title: 'Status',
                dataIndex: 'status',
                key: 'status',
                render: status => {
                  if (status === 'pending') return <Tag color="orange">Pending</Tag>;
                  if (status === 'accepted') return <Tag color="green">Accepted</Tag>;
                  return <Tag color="default">Rejected</Tag>;
                }
              },
              {
                title: 'Action',
                key: 'action',
                render: (_, record) => {
                  if (record.status !== 'pending') return null;
                  return (
                    <Space>
                      <Button
                        size="small"
                        type="primary"
                        loading={resolving === record.index}
                        onClick={() => handleResolve(record.index, 'accept')}
                      >
                        Accept AI
                      </Button>
                      <Button
                        size="small"
                        loading={resolving === record.index}
                        onClick={() => handleResolve(record.index, 'reject')}
                      >
                        Keep Current
                      </Button>
                    </Space>
                  );
                }
              }
            ]}
          />
        </Card>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/AIAnalysisSection.jsx
git commit -m "feat: add AIAnalysisSection component"
```

---

## Task 11: Frontend - Integrate into Case Detail Page

**Files:**
- Modify: `frontend/src/pages/CaseDetail.jsx`

**Step 1: Add import at top of file**

```javascript
import AIAnalysisSection from '../components/AIAnalysisSection';
```

**Step 2: Add AI Analysis section to the page layout**

Find the section where content cards are rendered (likely after the existing cards like Bid Information, Notes, etc.). Add:

```jsx
{/* AI Analysis Section - only show for upset_bid cases */}
{caseData?.classification === 'upset_bid' && (
  <div style={{ marginTop: 24 }}>
    <AIAnalysisSection caseId={id} />
  </div>
)}
```

**Step 3: Verify page still loads**

Start the frontend dev server and navigate to a case detail page. The AI Analysis section should appear for upset_bid cases.

**Step 4: Commit**

```bash
git add frontend/src/pages/CaseDetail.jsx
git commit -m "feat: integrate AI Analysis section into Case Detail page"
```

---

## Task 12: Frontend - Update Parties Tile with AI Defendant

**Files:**
- Modify: `frontend/src/pages/CaseDetail.jsx` (or the Parties component if separate)

**Step 1: Update Parties display to show AI-extracted defendant**

In the Parties section/component, check if AI analysis has a defendant_name and show it with an indicator:

```jsx
{/* In the Parties card/section, after the regular parties list */}
{analysis?.defendant_name && (
  <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #d9d9d9' }}>
    <Text type="secondary">AI Extracted: </Text>
    <Tag color="purple">{analysis.defendant_name}</Tag>
  </div>
)}
```

This requires passing the analysis data to the Parties component or fetching it there.

**Step 2: Commit**

```bash
git add frontend/src/pages/CaseDetail.jsx
git commit -m "feat: show AI-extracted defendant in Parties section"
```

---

## Task 13: End-to-End Test

**Step 1: Run the migration**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f migrations/add_case_analyses.sql
```

**Step 2: Manually queue a case for analysis**

```bash
PYTHONPATH=$(pwd) python -c "
from analysis.queue_processor import enqueue_analysis
from database.connection import get_session
from database.models import Case

with get_session() as session:
    # Get an upset_bid case
    case = session.query(Case).filter_by(classification='upset_bid').first()
    if case:
        print(f'Queuing case {case.id} ({case.case_number})')
        enqueue_analysis(case.id)
    else:
        print('No upset_bid cases found')
"
```

**Step 3: Process the queue**

```bash
PYTHONPATH=$(pwd) python -c "
from analysis.queue_processor import process_analysis_queue
result = process_analysis_queue(max_items=1)
print(result)
"
```

**Step 4: Check the result in database**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "SELECT id, case_id, status, cost_cents, completed_at FROM case_analyses ORDER BY id DESC LIMIT 5;"
```

**Step 5: Check the frontend**

Navigate to the case detail page for the analyzed case and verify the AI Analysis section displays correctly.

**Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete AI analysis module implementation"
```

---

## Summary

This implementation plan covers:

1. **Database**: Migration for `case_analyses` table with JSONB columns
2. **Backend**:
   - SQLAlchemy model
   - Prompt builder with red flag categories
   - Case analyzer with Claude API integration
   - Queue processor for batch processing
   - Integration with case_monitor for automatic triggering
   - Integration with daily_scrape for scheduled processing
   - API endpoints for fetching and resolving discrepancies
3. **Frontend**:
   - API client
   - AIAnalysisSection component with cards for summary, financials, red flags, discrepancies
   - Integration into Case Detail page
   - Parties tile update for AI-extracted defendant

Total: 13 tasks, each with clear steps and verification commands.
