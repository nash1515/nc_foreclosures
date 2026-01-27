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
