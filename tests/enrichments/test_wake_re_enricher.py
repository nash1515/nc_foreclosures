"""Tests for Wake County RE enricher."""

import pytest
from unittest import mock

from enrichments.wake_re.enricher import WakeREEnricher, enrich_case
from enrichments.common.base_enricher import EnrichmentResult


class TestWakeREEnricher:
    """Tests for WakeREEnricher class."""

    @mock.patch('enrichments.wake_re.enricher.fetch_pinlist_results')
    def test_enrich_with_parcel_id_success(self, mock_fetch, test_app, test_case_with_parcel):
        """Test successful enrichment via parcel ID."""
        mock_fetch.return_value = [{'account_id': '0379481'}]

        enricher = WakeREEnricher()
        result = enricher.enrich(test_case_with_parcel.id)

        assert result.success is True
        assert result.account_id == '0379481'
        assert 'Account.asp?id=0379481' in result.url

    @mock.patch('enrichments.wake_re.enricher.fetch_validate_address_results')
    @mock.patch('enrichments.wake_re.enricher.match_address_result')
    def test_enrich_with_address_fallback(self, mock_match, mock_fetch, test_app, test_case_with_address):
        """Test enrichment falls back to address when no parcel ID."""
        mock_fetch.return_value = [{'account_id': '0045436', 'stnum': '414', 'prefix': 'S', 'street_name': 'SALEM', 'etj': 'AP'}]
        mock_match.return_value = {'account_id': '0045436'}

        enricher = WakeREEnricher()
        result = enricher.enrich(test_case_with_address.id)

        assert result.success is True
        assert result.account_id == '0045436'

    @mock.patch('enrichments.wake_re.enricher.fetch_pinlist_results')
    def test_enrich_no_matches_logs_review(self, mock_fetch, test_app, test_case_with_parcel):
        """Test that zero matches logs to review queue."""
        mock_fetch.return_value = []

        enricher = WakeREEnricher()
        result = enricher.enrich(test_case_with_parcel.id)

        assert result.success is False
        assert result.review_needed is True


# Fixtures
@pytest.fixture
def test_app():
    """Create test Flask app context."""
    from web_app.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        yield app


@pytest.fixture
def test_case_with_parcel(test_app):
    """Create test case with parcel ID."""
    from database.models import Case
    from database.connection import get_session

    with get_session() as session:
        case = Case(
            case_number='TEST-PARCEL-001',
            county_code='910',
            county_name='Wake',
            parcel_id='0753018148',
        )
        session.add(case)
        session.commit()
        case_id = case.id

    # Yield the case (re-fetch to avoid detached instance issues)
    with get_session() as session:
        case = session.get(Case, case_id)
        yield case

    # Cleanup
    with get_session() as session:
        case = session.get(Case, case_id)
        if case:
            session.delete(case)
            session.commit()


@pytest.fixture
def test_case_with_address(test_app):
    """Create test case with address only."""
    from database.models import Case
    from database.connection import get_session

    with get_session() as session:
        case = Case(
            case_number='TEST-ADDR-001',
            county_code='910',
            county_name='Wake',
            property_address='414 S. Salem Street, Apex, NC 27502',
        )
        session.add(case)
        session.commit()
        case_id = case.id

    # Yield the case (re-fetch to avoid detached instance issues)
    with get_session() as session:
        case = session.get(Case, case_id)
        yield case

    # Cleanup
    with get_session() as session:
        case = session.get(Case, case_id)
        if case:
            session.delete(case)
            session.commit()
