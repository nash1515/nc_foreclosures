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

        # Store case ID and number before detachment
        case_id, case_number = test_case_with_documents

        with get_session() as session:
            # Add sale event to trigger upset_bid
            sale_event = CaseEvent(
                case_id=case_id,
                event_date=datetime.now().date(),
                event_type="Report of Foreclosure Sale",
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

            update_case_classification(case_id)

            # Run the Vision trigger synchronously for testing
            for target in targets:
                if target and 'vision' in target.__name__.lower():
                    target(case_id, case_number)

        # Verify case was updated with Vision data
        with get_session() as session:
            updated_case = session.query(Case).filter_by(id=case_id).first()

            # Vision should have set the address (was empty)
            assert updated_case.property_address == "789 Vision St, Cary, NC 27511"

            # Bid amount should be updated
            assert updated_case.current_bid_amount == Decimal('300000.00')

            # Documents should be marked as processed
            docs = session.query(Document).filter_by(case_id=case_id).all()
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
    from database.models import Case, Document, CaseEvent
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

        # Store case ID and number before detachment
        case_id = case.id
        case_number = case.case_number

    # Return case_id and case_number as tuple
    yield case_id, case_number

    # Cleanup
    with get_session() as session:
        session.query(Document).filter_by(case_id=case_id).delete()
        session.query(CaseEvent).filter_by(case_id=case_id).delete()
        case = session.query(Case).filter_by(id=case_id).first()
        if case:
            session.delete(case)
        session.commit()

    os.unlink(pdf_path)
