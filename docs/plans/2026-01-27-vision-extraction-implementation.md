# Vision Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Tesseract with Claude Vision for upset_bid cases to eliminate data quality issues.

**Architecture:** When a case enters upset_bid status, sweep all documents with Vision. New documents during upset period go directly to Vision (skip Tesseract). Track processing with `vision_processed_at` timestamp.

**Tech Stack:** Python, Claude Vision API (claude-sonnet-4-20250514), PostgreSQL, pytest

---

## Task 1: Database Migration

**Files:**
- Create: `migrations/add_vision_processed_at.sql`
- Modify: `database/models.py:163-183`

**Step 1: Create migration file**

Create `migrations/add_vision_processed_at.sql`:
```sql
-- Add vision_processed_at column to documents table
-- Tracks when a document was processed by Claude Vision for structured extraction

ALTER TABLE documents ADD COLUMN IF NOT EXISTS vision_processed_at TIMESTAMP;

COMMENT ON COLUMN documents.vision_processed_at IS 'Timestamp when document was processed by Claude Vision';

-- Index for efficient filtering of unprocessed documents
CREATE INDEX IF NOT EXISTS idx_documents_vision_processed_at ON documents(vision_processed_at);
```

**Step 2: Run migration**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f migrations/add_vision_processed_at.sql
```

Expected: `ALTER TABLE`, `COMMENT`, `CREATE INDEX`

**Step 3: Update SQLAlchemy model**

In `database/models.py`, add to `Document` class after `extraction_attempted_at`:
```python
    vision_processed_at = Column(TIMESTAMP)  # When Vision extraction completed
```

**Step 4: Verify column exists**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "\d documents"
```

Expected: `vision_processed_at | timestamp without time zone`

**Step 5: Commit**

```bash
git add migrations/add_vision_processed_at.sql database/models.py
git commit -m "feat: add vision_processed_at column to documents table"
```

---

## Task 2: Create Vision Extraction Module

**Files:**
- Create: `ocr/vision_extraction.py`
- Create: `tests/ocr/test_vision_extraction.py`

**Step 1: Write the failing test**

Create `tests/ocr/test_vision_extraction.py`:
```python
"""Tests for Vision extraction module."""
import pytest
from unittest import mock
from decimal import Decimal
import json


class TestExtractStructuredData:
    """Tests for extract_structured_data function."""

    @mock.patch('ocr.vision_extraction.anthropic.Anthropic')
    def test_extracts_all_fields_from_report_of_sale(self, mock_anthropic_class, test_app):
        """Test extraction from a Report of Sale document."""
        from ocr.vision_extraction import extract_structured_data

        # Mock Claude response
        mock_response = mock.MagicMock()
        mock_response.content = [mock.MagicMock(text=json.dumps({
            "property_address": "123 Main St, Raleigh, NC 27601",
            "legal_description": "Lot 5, Block B, Sunrise Subdivision",
            "bid_amount": 245000.00,
            "minimum_next_bid": 250000.00,
            "deposit_required": 750.00,
            "sale_date": "2026-01-15",
            "trustee_name": "John Smith",
            "attorney_name": "Jane Doe",
            "attorney_phone": "919-555-1234",
            "attorney_email": "jdoe@lawfirm.com",
            "document_type": "Report of Foreclosure Sale",
            "confidence": "high",
            "notes": None
        }))]
        mock_response.usage = mock.MagicMock(input_tokens=1000, output_tokens=200)

        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Call with test PDF path (will be mocked)
        with mock.patch('ocr.vision_extraction._pdf_to_base64_images', return_value=['base64image']):
            result = extract_structured_data('/fake/path.pdf')

        assert result['property_address'] == "123 Main St, Raleigh, NC 27601"
        assert result['bid_amount'] == Decimal('245000.00')
        assert result['sale_date'] == "2026-01-15"
        assert result['confidence'] == "high"

    @mock.patch('ocr.vision_extraction.anthropic.Anthropic')
    def test_returns_nulls_for_missing_fields(self, mock_anthropic_class, test_app):
        """Test that missing fields return None, not guessed values."""
        from ocr.vision_extraction import extract_structured_data

        mock_response = mock.MagicMock()
        mock_response.content = [mock.MagicMock(text=json.dumps({
            "property_address": "456 Oak Ave, Durham, NC 27701",
            "legal_description": None,
            "bid_amount": 180000.00,
            "minimum_next_bid": None,
            "deposit_required": None,
            "sale_date": "2026-01-10",
            "trustee_name": None,
            "attorney_name": None,
            "attorney_phone": None,
            "attorney_email": None,
            "document_type": "Notice of Sale",
            "confidence": "medium",
            "notes": "Document is a notice, not a sale report"
        }))]
        mock_response.usage = mock.MagicMock(input_tokens=800, output_tokens=150)

        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        with mock.patch('ocr.vision_extraction._pdf_to_base64_images', return_value=['base64image']):
            result = extract_structured_data('/fake/path.pdf')

        assert result['property_address'] == "456 Oak Ave, Durham, NC 27701"
        assert result['legal_description'] is None
        assert result['minimum_next_bid'] is None
        assert result['trustee_name'] is None

    @mock.patch('ocr.vision_extraction.anthropic.Anthropic')
    def test_handles_api_error_gracefully(self, mock_anthropic_class, test_app):
        """Test graceful handling of API errors."""
        from ocr.vision_extraction import extract_structured_data
        import anthropic

        mock_client = mock.MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="Rate limited",
            request=mock.MagicMock(),
            body=None
        )
        mock_anthropic_class.return_value = mock_client

        with mock.patch('ocr.vision_extraction._pdf_to_base64_images', return_value=['base64image']):
            result = extract_structured_data('/fake/path.pdf')

        # Should return empty result, not raise
        assert result['property_address'] is None
        assert result['error'] is not None


@pytest.fixture
def test_app():
    """Create test Flask app context."""
    from web_app.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        yield app
```

**Step 2: Run test to verify it fails**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python -m pytest tests/ocr/test_vision_extraction.py -v
```

Expected: `ModuleNotFoundError: No module named 'ocr.vision_extraction'`

**Step 3: Write minimal implementation**

Create `ocr/vision_extraction.py`:
```python
"""
Vision extraction module for structured data extraction from PDFs.

Uses Claude Vision to extract structured data from foreclosure documents.
This is the primary extraction method for upset_bid cases.
"""
import os
import json
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime

import anthropic
from pdf2image import convert_from_path
import base64
import io

from common.logger import setup_logger

logger = setup_logger(__name__)

VISION_MODEL = "claude-sonnet-4-20250514"
MAX_PAGES = 3  # First 3 pages + last if >3

EXTRACTION_PROMPT = """You are extracting structured data from a North Carolina foreclosure document.

Analyze this document image and extract the following fields. Return ONLY valid JSON with these exact keys:

{
    "property_address": "Full street address with city, state, zip - or null if not found",
    "legal_description": "Legal property description (lot/block/subdivision) - or null if not found",
    "bid_amount": <number - winning/current bid amount in dollars, no $ sign - or null>,
    "minimum_next_bid": <number - minimum amount for next upset bid - or null>,
    "deposit_required": <number - required deposit amount - or null>,
    "sale_date": "YYYY-MM-DD format - date of foreclosure sale - or null",
    "trustee_name": "Name of substitute trustee - or null",
    "attorney_name": "Foreclosure attorney name - or null",
    "attorney_phone": "Attorney phone number - or null",
    "attorney_email": "Attorney email address - or null",
    "document_type": "Your assessment of document type (Report of Foreclosure Sale, Notice of Upset Bid, etc.)",
    "confidence": "high/medium/low - your confidence in the extraction accuracy",
    "notes": "Any issues or uncertainties - or null"
}

IMPORTANT:
- Return null for any field you cannot find or are uncertain about
- Do NOT guess or infer missing information
- For amounts, extract the numeric value only (no $ or commas)
- For addresses, include full address if available (street, city, state, zip)
- Property addresses often appear after "property located at" or "Property Address"
- Bid amounts often appear after "Amount Bid" or "Highest Bid"

Return ONLY the JSON object, no other text."""


def _pdf_to_base64_images(pdf_path: str, max_pages: int = MAX_PAGES) -> list:
    """Convert PDF pages to base64-encoded PNG images."""
    try:
        images = convert_from_path(pdf_path, dpi=200)

        # If more than max_pages, take first (max-1) + last
        if len(images) > max_pages:
            selected = images[:max_pages-1] + [images[-1]]
        else:
            selected = images[:max_pages]

        base64_images = []
        for img in selected:
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            base64_images.append(base64.b64encode(buffer.getvalue()).decode('utf-8'))

        return base64_images
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        return []


def extract_structured_data(pdf_path: str) -> Dict[str, Any]:
    """
    Extract structured data from a PDF using Claude Vision.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dict with extracted fields. Missing fields are None.
        Includes 'error' key if extraction failed.
        Includes 'cost_cents' and 'tokens' for tracking.
    """
    result = {
        'property_address': None,
        'legal_description': None,
        'bid_amount': None,
        'minimum_next_bid': None,
        'deposit_required': None,
        'sale_date': None,
        'trustee_name': None,
        'attorney_name': None,
        'attorney_phone': None,
        'attorney_email': None,
        'document_type': None,
        'confidence': None,
        'notes': None,
        'error': None,
        'cost_cents': 0,
        'tokens': {'input': 0, 'output': 0}
    }

    # Convert PDF to images
    images = _pdf_to_base64_images(pdf_path)
    if not images:
        result['error'] = "Failed to convert PDF to images"
        return result

    # Build message content with images
    content = []
    for i, img_base64 in enumerate(images):
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_base64
            }
        })
    content.append({"type": "text", "text": EXTRACTION_PROMPT})

    try:
        client = anthropic.Anthropic()

        response = client.messages.create(
            model=VISION_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}]
        )

        # Track usage
        result['tokens'] = {
            'input': response.usage.input_tokens,
            'output': response.usage.output_tokens
        }
        # Rough cost estimate: $3/M input, $15/M output for Sonnet
        result['cost_cents'] = (
            (response.usage.input_tokens * 0.003 / 10) +
            (response.usage.output_tokens * 0.015 / 10)
        )

        # Parse JSON response
        response_text = response.content[0].text.strip()

        # Handle markdown code blocks
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]

        data = json.loads(response_text)

        # Map extracted data to result
        result['property_address'] = data.get('property_address')
        result['legal_description'] = data.get('legal_description')
        result['sale_date'] = data.get('sale_date')
        result['trustee_name'] = data.get('trustee_name')
        result['attorney_name'] = data.get('attorney_name')
        result['attorney_phone'] = data.get('attorney_phone')
        result['attorney_email'] = data.get('attorney_email')
        result['document_type'] = data.get('document_type')
        result['confidence'] = data.get('confidence')
        result['notes'] = data.get('notes')

        # Convert numeric fields to Decimal
        if data.get('bid_amount') is not None:
            result['bid_amount'] = Decimal(str(data['bid_amount']))
        if data.get('minimum_next_bid') is not None:
            result['minimum_next_bid'] = Decimal(str(data['minimum_next_bid']))
        if data.get('deposit_required') is not None:
            result['deposit_required'] = Decimal(str(data['deposit_required']))

        logger.info(f"Vision extraction complete: {result['document_type']}, confidence={result['confidence']}")

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        result['error'] = f"API error: {str(e)}"
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Vision response as JSON: {e}")
        result['error'] = f"JSON parse error: {str(e)}"
    except Exception as e:
        logger.error(f"Vision extraction failed: {e}")
        result['error'] = f"Extraction error: {str(e)}"

    return result


def process_document_with_vision(document_id: int) -> Dict[str, Any]:
    """
    Process a single document with Vision and update tracking.

    Args:
        document_id: Database ID of the document

    Returns:
        Extraction result dict
    """
    from database.connection import get_session
    from database.models import Document

    with get_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            return {'error': f'Document {document_id} not found'}

        if not doc.file_path or not os.path.exists(doc.file_path):
            return {'error': f'PDF file not found: {doc.file_path}'}

        # Extract data
        result = extract_structured_data(doc.file_path)

        # Update tracking timestamp
        doc.vision_processed_at = datetime.utcnow()
        session.commit()

        logger.info(f"Document {document_id} processed with Vision (cost: ${result['cost_cents']:.2f})")

    return result


def sweep_case_documents(case_id: int, force: bool = False) -> Dict[str, Any]:
    """
    Process all documents for a case with Vision.

    Args:
        case_id: Database ID of the case
        force: If True, reprocess even if already processed

    Returns:
        Dict with 'documents_processed', 'total_cost_cents', 'results'
    """
    from database.connection import get_session
    from database.models import Document, Case

    summary = {
        'documents_processed': 0,
        'documents_skipped': 0,
        'total_cost_cents': 0,
        'results': [],
        'errors': []
    }

    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            summary['errors'].append(f'Case {case_id} not found')
            return summary

        # Get documents to process
        query = session.query(Document).filter_by(case_id=case_id)
        if not force:
            query = query.filter(Document.vision_processed_at.is_(None))

        documents = query.all()

        logger.info(f"Vision sweep for case {case.case_number}: {len(documents)} documents to process")

        for doc in documents:
            if not doc.file_path or not os.path.exists(doc.file_path):
                summary['documents_skipped'] += 1
                summary['errors'].append(f"Doc {doc.id}: file not found")
                continue

            result = extract_structured_data(doc.file_path)

            # Update tracking
            doc.vision_processed_at = datetime.utcnow()

            summary['documents_processed'] += 1
            summary['total_cost_cents'] += result.get('cost_cents', 0)
            summary['results'].append({
                'document_id': doc.id,
                'document_name': doc.document_name,
                **result
            })

            if result.get('error'):
                summary['errors'].append(f"Doc {doc.id}: {result['error']}")

        session.commit()

    logger.info(f"Vision sweep complete: {summary['documents_processed']} docs, ${summary['total_cost_cents']:.2f}")

    return summary


def update_case_from_vision_results(case_id: int, results: list) -> bool:
    """
    Update case record with Vision-extracted data.

    Uses latest document data. Null values don't overwrite existing.
    Property address uses first-set-wins (sticky).

    Args:
        case_id: Database ID of the case
        results: List of extraction results from sweep_case_documents

    Returns:
        True if case was updated
    """
    from database.connection import get_session
    from database.models import Case

    if not results:
        return False

    # Sort by document_id descending (newer documents first)
    sorted_results = sorted(results, key=lambda x: x.get('document_id', 0), reverse=True)

    # Merge results - later values fill in gaps
    merged = {}
    fields = ['property_address', 'legal_description', 'bid_amount',
              'minimum_next_bid', 'deposit_required', 'sale_date',
              'trustee_name', 'attorney_name', 'attorney_phone', 'attorney_email']

    for field in fields:
        for result in sorted_results:
            if result.get(field) is not None:
                merged[field] = result[field]
                break

    if not merged:
        return False

    with get_session() as session:
        case = session.query(Case).filter_by(id=case_id).first()
        if not case:
            return False

        updated = False

        # Property address: first-set-wins (sticky)
        if 'property_address' in merged and not case.property_address:
            case.property_address = merged['property_address']
            updated = True
            logger.info(f"Case {case.case_number}: Set property_address via Vision")

        # Financial fields: always update if we have new data
        if 'bid_amount' in merged and merged['bid_amount']:
            case.current_bid_amount = merged['bid_amount']
            updated = True

        if 'minimum_next_bid' in merged and merged['minimum_next_bid']:
            case.minimum_next_bid = merged['minimum_next_bid']
            updated = True

        # Other fields: update if currently empty
        if 'legal_description' in merged and not case.legal_description:
            case.legal_description = merged['legal_description']
            updated = True

        if 'sale_date' in merged and not case.sale_date:
            from datetime import datetime
            try:
                case.sale_date = datetime.strptime(merged['sale_date'], '%Y-%m-%d').date()
                updated = True
            except (ValueError, TypeError):
                pass

        if updated:
            session.commit()
            logger.info(f"Case {case.case_number}: Updated from Vision extraction")

        return updated
```

**Step 4: Run tests to verify they pass**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python -m pytest tests/ocr/test_vision_extraction.py -v
```

Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add ocr/vision_extraction.py tests/ocr/test_vision_extraction.py
git commit -m "feat: add Vision extraction module for structured data"
```

---

## Task 3: Integrate Vision into Classifier Trigger

**Files:**
- Modify: `extraction/classifier.py:27-67`
- Create: `tests/extraction/test_classifier_vision_trigger.py`

**Step 1: Write the failing test**

Create `tests/extraction/test_classifier_vision_trigger.py`:
```python
"""Tests for Vision extraction trigger in classifier."""
import pytest
from unittest import mock


class TestVisionTriggerOnUpsetBid:
    """Tests for Vision sweep trigger when case enters upset_bid."""

    @mock.patch('extraction.classifier._trigger_vision_extraction_async')
    @mock.patch('extraction.classifier._trigger_enrichment_async')
    def test_triggers_vision_sweep_on_upset_bid_transition(
        self, mock_enrichment, mock_vision, test_app, test_case_upcoming
    ):
        """Test that Vision sweep is triggered when case transitions to upset_bid."""
        from extraction.classifier import update_case_classification
        from database.connection import get_session
        from database.models import Case, CaseEvent
        from datetime import datetime, timedelta

        with get_session() as session:
            case = session.query(Case).filter_by(id=test_case_upcoming.id).first()

            # Add a sale event to trigger upset_bid classification
            sale_event = CaseEvent(
                case_id=case.id,
                event_date=datetime.now().date(),
                event_description="Report of Foreclosure Sale filed"
            )
            session.add(sale_event)
            session.commit()
            case_id = case.id
            case_number = case.case_number

        # Run classification
        update_case_classification(case_id)

        # Verify Vision trigger was called
        mock_vision.assert_called_once()
        call_args = mock_vision.call_args[0]
        assert call_args[0] == case_id


@pytest.fixture
def test_app():
    """Create test Flask app context."""
    from web_app.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        yield app


@pytest.fixture
def test_case_upcoming(test_app):
    """Create test case with upcoming status."""
    from database.models import Case
    from database.connection import get_session

    with get_session() as session:
        case = Case(
            case_number='TEST-2026-VISION-001',
            county_code='WAKE',
            county_name='Wake',
            classification='upcoming'
        )
        session.add(case)
        session.commit()
        session.refresh(case)
        yield case

        # Cleanup
        session.delete(case)
        session.commit()
```

**Step 2: Run test to verify it fails**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python -m pytest tests/extraction/test_classifier_vision_trigger.py -v
```

Expected: `AttributeError: module 'extraction.classifier' has no attribute '_trigger_vision_extraction_async'`

**Step 3: Add Vision trigger to classifier**

In `extraction/classifier.py`, add new function after `_trigger_enrichment_async` (around line 67):

```python
def _trigger_vision_extraction_async(case_id: int, case_number: str):
    """
    Trigger Vision extraction sweep for all case documents in background thread.

    This is called when a case transitions to upset_bid status.
    Runs asynchronously to avoid blocking the classification process.

    Args:
        case_id: Database ID of the case
        case_number: Case number for logging
    """
    try:
        from ocr.vision_extraction import sweep_case_documents, update_case_from_vision_results

        logger.info(f"  Starting Vision sweep for case {case_number}")

        # Sweep all unprocessed documents
        sweep_result = sweep_case_documents(case_id)

        if sweep_result['documents_processed'] > 0:
            # Update case with extracted data
            update_case_from_vision_results(case_id, sweep_result['results'])
            logger.info(
                f"  Vision sweep complete for {case_number}: "
                f"{sweep_result['documents_processed']} docs, "
                f"${sweep_result['total_cost_cents']:.2f}"
            )
        else:
            logger.info(f"  Vision sweep: no documents to process for {case_number}")

        if sweep_result['errors']:
            for err in sweep_result['errors']:
                logger.warning(f"  Vision sweep warning: {err}")

    except Exception as e:
        logger.error(f"  Vision extraction failed for case {case_number}: {e}")
```

**Step 4: Add Vision trigger call in update_case_classification**

Find the section around line 788-798 where enrichment is triggered, and add Vision trigger:

```python
            if old_classification != classification:
                if classification == 'upset_bid':
                    # Trigger enrichment
                    Thread(
                        target=_trigger_enrichment_async,
                        args=(case.id, case.case_number),
                        daemon=True
                    ).start()
                    logger.info(f"  Case {case.case_number}: Queued enrichment")

                    # Trigger Vision extraction sweep
                    Thread(
                        target=_trigger_vision_extraction_async,
                        args=(case.id, case.case_number),
                        daemon=True
                    ).start()
                    logger.info(f"  Case {case.case_number}: Queued Vision extraction")
```

**Step 5: Run test to verify it passes**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python -m pytest tests/extraction/test_classifier_vision_trigger.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add extraction/classifier.py tests/extraction/test_classifier_vision_trigger.py
git commit -m "feat: trigger Vision sweep when case enters upset_bid"
```

---

## Task 4: Route New Documents to Vision During Upset Period

**Files:**
- Modify: `ocr/processor.py:123-174`
- Create: `tests/ocr/test_processor_vision_routing.py`

**Step 1: Write the failing test**

Create `tests/ocr/test_processor_vision_routing.py`:
```python
"""Tests for Vision routing in document processor."""
import pytest
from unittest import mock


class TestVisionRoutingForUpsetBid:
    """Tests for routing upset_bid documents to Vision."""

    @mock.patch('ocr.processor.process_document_with_vision')
    @mock.patch('ocr.processor.extract_text_from_pdf')
    def test_uses_vision_for_upset_bid_case(
        self, mock_tesseract, mock_vision, test_app, test_upset_bid_case_with_doc
    ):
        """Test that documents for upset_bid cases use Vision, not Tesseract."""
        from ocr.processor import process_document

        mock_vision.return_value = {
            'property_address': '123 Test St',
            'bid_amount': None,
            'error': None
        }

        case, doc = test_upset_bid_case_with_doc

        process_document(doc.id, run_extraction=False)

        # Vision should be called, not Tesseract
        mock_vision.assert_called_once()
        mock_tesseract.assert_not_called()

    @mock.patch('ocr.processor.process_document_with_vision')
    @mock.patch('ocr.processor.extract_text_from_pdf')
    def test_uses_tesseract_for_upcoming_case(
        self, mock_tesseract, mock_vision, test_app, test_upcoming_case_with_doc
    ):
        """Test that documents for upcoming cases use Tesseract, not Vision."""
        from ocr.processor import process_document

        mock_tesseract.return_value = ('Some OCR text', 'ocr')

        case, doc = test_upcoming_case_with_doc

        process_document(doc.id, run_extraction=False)

        # Tesseract should be called, not Vision
        mock_tesseract.assert_called_once()
        mock_vision.assert_not_called()


@pytest.fixture
def test_app():
    """Create test Flask app context."""
    from web_app.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        yield app


@pytest.fixture
def test_upset_bid_case_with_doc(test_app):
    """Create upset_bid case with a document."""
    from database.models import Case, Document
    from database.connection import get_session
    import tempfile
    import os

    # Create a dummy PDF file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b'%PDF-1.4 dummy')
        pdf_path = f.name

    with get_session() as session:
        case = Case(
            case_number='TEST-UPSET-001',
            county_code='WAKE',
            county_name='Wake',
            classification='upset_bid'
        )
        session.add(case)
        session.flush()

        doc = Document(
            case_id=case.id,
            document_name='Test Report of Sale.pdf',
            file_path=pdf_path
        )
        session.add(doc)
        session.commit()
        session.refresh(case)
        session.refresh(doc)

        yield case, doc

        # Cleanup
        session.delete(doc)
        session.delete(case)
        session.commit()

    os.unlink(pdf_path)


@pytest.fixture
def test_upcoming_case_with_doc(test_app):
    """Create upcoming case with a document."""
    from database.models import Case, Document
    from database.connection import get_session
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b'%PDF-1.4 dummy')
        pdf_path = f.name

    with get_session() as session:
        case = Case(
            case_number='TEST-UPCOMING-001',
            county_code='WAKE',
            county_name='Wake',
            classification='upcoming'
        )
        session.add(case)
        session.flush()

        doc = Document(
            case_id=case.id,
            document_name='Test Notice.pdf',
            file_path=pdf_path
        )
        session.add(doc)
        session.commit()
        session.refresh(case)
        session.refresh(doc)

        yield case, doc

        # Cleanup
        session.delete(doc)
        session.delete(case)
        session.commit()

    os.unlink(pdf_path)
```

**Step 2: Run test to verify it fails**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python -m pytest tests/ocr/test_processor_vision_routing.py -v
```

Expected: FAIL (Vision not called, Tesseract called for both)

**Step 3: Modify process_document to route based on classification**

In `ocr/processor.py`, modify the `process_document` function. Find where it calls `extract_text_from_pdf` and add classification check:

```python
def process_document(document_id: int, run_extraction: bool = True) -> bool:
    """
    Process a document by ID - extract text and update database.

    For upset_bid cases, uses Vision extraction for better accuracy.
    For other cases, uses Tesseract OCR.

    Args:
        document_id: Database ID of the document to process
        run_extraction: If True, auto-trigger data extraction after OCR

    Returns:
        bool: True if processing succeeded
    """
    from database.connection import get_session
    from database.models import Document, Case

    with get_session() as session:
        doc = session.query(Document).filter_by(id=document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return False

        # Check if already processed
        if doc.ocr_text:
            logger.info(f"Document {document_id} already has OCR text, skipping")
            return True

        if not doc.file_path:
            logger.error(f"Document {document_id} has no file path")
            return False

        # Get case to check classification
        case = session.query(Case).filter_by(id=doc.case_id).first()

        # Route to Vision for upset_bid cases
        if case and case.classification == 'upset_bid':
            logger.info(f"Document {document_id}: Using Vision (upset_bid case)")
            from ocr.vision_extraction import process_document_with_vision
            result = process_document_with_vision(document_id)

            # Store any text representation for compatibility
            if result.get('document_type'):
                doc.ocr_text = f"[Vision extracted: {result['document_type']}]"
                session.commit()

            # Run case extraction if requested
            if run_extraction and not result.get('error'):
                _run_extraction_for_case(doc.case_id)

            return not result.get('error')

        # Standard Tesseract path for non-upset_bid cases
        logger.info(f"Document {document_id}: Using Tesseract OCR")
        text, method = extract_text_from_pdf(doc.file_path)

        if text:
            doc.ocr_text = text
            session.commit()
            logger.info(f"Document {document_id} processed with {method}: {len(text)} chars")

            if run_extraction:
                _run_extraction_for_case(doc.case_id)

            return True
        else:
            logger.warning(f"Document {document_id}: No text extracted")
            return False
```

**Step 4: Run test to verify it passes**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python -m pytest tests/ocr/test_processor_vision_routing.py -v
```

Expected: Both tests PASS

**Step 5: Commit**

```bash
git add ocr/processor.py tests/ocr/test_processor_vision_routing.py
git commit -m "feat: route upset_bid documents to Vision extraction"
```

---

## Task 5: Create Backfill Script

**Files:**
- Create: `scripts/backfill_vision_extraction.py`

**Step 1: Create the backfill script**

Create `scripts/backfill_vision_extraction.py`:
```python
#!/usr/bin/env python3
"""
Backfill Vision extraction for existing upset_bid cases.

One-time script to process all documents for cases currently in upset_bid status.
Run after deploying Vision extraction feature.

Usage:
    PYTHONPATH=$(pwd) venv/bin/python scripts/backfill_vision_extraction.py [--dry-run] [--limit N]
"""
import argparse
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/home/ahn/projects/nc_foreclosures')

from database.connection import get_session
from database.models import Case, Document
from ocr.vision_extraction import sweep_case_documents, update_case_from_vision_results
from common.logger import setup_logger

logger = setup_logger(__name__)


def backfill_vision_extraction(dry_run: bool = False, limit: int = None):
    """
    Process all upset_bid cases with Vision extraction.

    Args:
        dry_run: If True, only report what would be done
        limit: Max number of cases to process (None = all)
    """
    with get_session() as session:
        # Get all upset_bid cases
        query = session.query(Case).filter_by(classification='upset_bid')
        if limit:
            query = query.limit(limit)

        cases = query.all()

        logger.info(f"Found {len(cases)} upset_bid cases to process")

        total_docs = 0
        total_cost = 0.0

        for case in cases:
            # Count unprocessed documents
            unprocessed = session.query(Document).filter(
                Document.case_id == case.id,
                Document.vision_processed_at.is_(None),
                Document.file_path.isnot(None)
            ).count()

            if unprocessed == 0:
                logger.info(f"  {case.case_number}: No unprocessed documents, skipping")
                continue

            logger.info(f"  {case.case_number}: {unprocessed} documents to process")

            if dry_run:
                total_docs += unprocessed
                # Estimate cost: ~$0.02 per document
                total_cost += unprocessed * 0.02
                continue

            # Process the case
            result = sweep_case_documents(case.id)

            if result['documents_processed'] > 0:
                update_case_from_vision_results(case.id, result['results'])

            total_docs += result['documents_processed']
            total_cost += result['total_cost_cents'] / 100.0

            if result['errors']:
                for err in result['errors']:
                    logger.warning(f"    Error: {err}")

            logger.info(
                f"    Processed {result['documents_processed']} docs, "
                f"${result['total_cost_cents']/100:.2f}"
            )

    # Summary
    logger.info("=" * 50)
    if dry_run:
        logger.info(f"DRY RUN - Would process {total_docs} documents")
        logger.info(f"Estimated cost: ${total_cost:.2f}")
    else:
        logger.info(f"Backfill complete: {total_docs} documents processed")
        logger.info(f"Total cost: ${total_cost:.2f}")


def main():
    parser = argparse.ArgumentParser(
        description='Backfill Vision extraction for upset_bid cases'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Report what would be done without processing'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of cases to process'
    )

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Vision Extraction Backfill")
    logger.info(f"Started: {datetime.now().isoformat()}")
    if args.dry_run:
        logger.info("MODE: Dry run")
    logger.info("=" * 50)

    backfill_vision_extraction(dry_run=args.dry_run, limit=args.limit)


if __name__ == '__main__':
    main()
```

**Step 2: Make executable**

```bash
chmod +x scripts/backfill_vision_extraction.py
```

**Step 3: Test dry run**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python scripts/backfill_vision_extraction.py --dry-run
```

Expected: Lists upset_bid cases and estimated document counts/cost

**Step 4: Commit**

```bash
git add scripts/backfill_vision_extraction.py
git commit -m "feat: add backfill script for Vision extraction"
```

---

## Task 6: Integration Test

**Files:**
- Create: `tests/test_vision_extraction_integration.py`

**Step 1: Create integration test**

Create `tests/test_vision_extraction_integration.py`:
```python
"""Integration tests for Vision extraction pipeline."""
import pytest
from unittest import mock
from decimal import Decimal
import json


class TestVisionExtractionIntegration:
    """End-to-end tests for Vision extraction flow."""

    @mock.patch('ocr.vision_extraction.anthropic.Anthropic')
    @mock.patch('ocr.vision_extraction._pdf_to_base64_images')
    def test_full_flow_case_enters_upset_bid(
        self, mock_images, mock_anthropic_class, test_app, test_case_with_documents
    ):
        """Test complete flow: case enters upset_bid → Vision sweep → case updated."""
        from extraction.classifier import update_case_classification
        from database.connection import get_session
        from database.models import Case, CaseEvent, Document
        from datetime import datetime
        import time

        # Setup mocks
        mock_images.return_value = ['base64image']

        mock_response = mock.MagicMock()
        mock_response.content = [mock.MagicMock(text=json.dumps({
            "property_address": "789 Vision St, Cary, NC 27511",
            "legal_description": "Lot 10, Test Subdivision",
            "bid_amount": 300000.00,
            "minimum_next_bid": 305000.00,
            "deposit_required": 750.00,
            "sale_date": "2026-01-20",
            "trustee_name": "Vision Trustee",
            "attorney_name": "Vision Attorney",
            "attorney_phone": "919-555-9999",
            "attorney_email": "vision@test.com",
            "document_type": "Report of Foreclosure Sale",
            "confidence": "high",
            "notes": None
        }))]
        mock_response.usage = mock.MagicMock(input_tokens=1000, output_tokens=200)

        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        case = test_case_with_documents

        with get_session() as session:
            # Add sale event to trigger upset_bid
            sale_event = CaseEvent(
                case_id=case.id,
                event_date=datetime.now().date(),
                event_description="Report of Foreclosure Sale filed"
            )
            session.add(sale_event)
            session.commit()

        # Run classification (triggers Vision sweep in background)
        with mock.patch('extraction.classifier.Thread') as mock_thread:
            # Capture the thread targets
            targets = []
            def capture_thread(*args, **kwargs):
                t = mock.MagicMock()
                targets.append(kwargs.get('target'))
                return t
            mock_thread.side_effect = capture_thread

            update_case_classification(case.id)

            # Run the Vision trigger synchronously for testing
            for target in targets:
                if target and 'vision' in target.__name__.lower():
                    target(case.id, case.case_number)

        # Verify case was updated with Vision data
        with get_session() as session:
            updated_case = session.query(Case).filter_by(id=case.id).first()

            # Vision should have set the address (was empty)
            assert updated_case.property_address == "789 Vision St, Cary, NC 27511"

            # Bid amount should be updated
            assert updated_case.current_bid_amount == Decimal('300000.00')

            # Documents should be marked as processed
            docs = session.query(Document).filter_by(case_id=case.id).all()
            for doc in docs:
                if doc.file_path:
                    assert doc.vision_processed_at is not None


@pytest.fixture
def test_app():
    """Create test Flask app context."""
    from web_app.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        yield app


@pytest.fixture
def test_case_with_documents(test_app):
    """Create test case with documents for integration test."""
    from database.models import Case, Document
    from database.connection import get_session
    import tempfile
    import os

    # Create dummy PDF
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(b'%PDF-1.4 dummy content')
        pdf_path = f.name

    with get_session() as session:
        case = Case(
            case_number='TEST-INTEGRATION-001',
            county_code='WAKE',
            county_name='Wake',
            classification='upcoming',
            property_address=None  # Empty, should be filled by Vision
        )
        session.add(case)
        session.flush()

        doc = Document(
            case_id=case.id,
            document_name='Report of Foreclosure Sale.pdf',
            file_path=pdf_path
        )
        session.add(doc)
        session.commit()
        session.refresh(case)

        yield case

        # Cleanup
        session.query(Document).filter_by(case_id=case.id).delete()
        session.query(CaseEvent).filter_by(case_id=case.id).delete()
        session.delete(case)
        session.commit()

    os.unlink(pdf_path)
```

**Step 2: Run integration test**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python -m pytest tests/test_vision_extraction_integration.py -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_vision_extraction_integration.py
git commit -m "test: add Vision extraction integration test"
```

---

## Task 7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add Vision extraction to Recent Changes section**

Add under "Recent Changes" in CLAUDE.md:
```markdown
### Session 37 (Jan 27)
- **Vision extraction for upset_bid** - Claude Vision replaces Tesseract for upset_bid cases
- Documents processed with Vision when case enters upset_bid status
- New documents during upset period go directly to Vision
- Backfill script for existing 39 upset_bid cases
```

**Step 2: Add to Architecture section**

Under Modules, update the `ocr/` entry:
```markdown
- `ocr/` - PDF text extraction (Tesseract for upcoming, Claude Vision for upset_bid)
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Vision extraction to CLAUDE.md"
```

---

## Task 8: Run Backfill (Production)

**Step 1: Run dry-run first**

```bash
cd /home/ahn/projects/nc_foreclosures
PYTHONPATH=$(pwd) venv/bin/python scripts/backfill_vision_extraction.py --dry-run
```

Review output for expected cost and document counts.

**Step 2: Run actual backfill**

```bash
PYTHONPATH=$(pwd) venv/bin/python scripts/backfill_vision_extraction.py
```

**Step 3: Verify results**

```bash
PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -c "
SELECT
    c.case_number,
    c.property_address,
    c.current_bid_amount,
    COUNT(d.id) as docs,
    COUNT(d.vision_processed_at) as vision_processed
FROM cases c
LEFT JOIN documents d ON d.case_id = c.id
WHERE c.classification = 'upset_bid'
GROUP BY c.id
ORDER BY c.case_number
LIMIT 10;
"
```

---

## Summary

| Task | Description | Estimated Time |
|------|-------------|----------------|
| 1 | Database migration | 5 min |
| 2 | Vision extraction module + tests | 20 min |
| 3 | Classifier trigger integration | 15 min |
| 4 | Processor routing | 15 min |
| 5 | Backfill script | 10 min |
| 6 | Integration test | 10 min |
| 7 | Documentation | 5 min |
| 8 | Run backfill | 10 min |

**Total: ~90 minutes**

**Post-deployment verification:**
1. Check a few upset_bid cases have Vision-extracted addresses
2. Monitor costs in logs
3. Verify new documents during upset period use Vision
