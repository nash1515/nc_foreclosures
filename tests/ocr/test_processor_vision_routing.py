"""Tests for Vision routing in document processor."""
import pytest
from unittest import mock


class TestVisionRoutingForUpsetBid:
    """Tests for routing upset_bid documents to Vision."""

    @mock.patch('ocr.vision_extraction.process_document_with_vision')
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

    @mock.patch('ocr.vision_extraction.process_document_with_vision')
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
