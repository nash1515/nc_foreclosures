"""Tests for Vision extraction trigger in classifier."""
import pytest
from unittest import mock


class TestVisionTriggerOnUpsetBid:
    """Tests for Vision sweep trigger when case enters upset_bid."""

    @mock.patch('extraction.classifier.classify_case')
    @mock.patch('extraction.classifier.Thread')
    def test_triggers_vision_sweep_on_upset_bid_transition(
        self, mock_thread, mock_classify, test_app, test_case_upcoming
    ):
        """Test that Vision sweep is triggered when case transitions to upset_bid."""
        from extraction.classifier import update_case_classification, _trigger_enrichment_async, _trigger_vision_extraction_async
        from database.connection import get_session
        from database.models import Case, CaseEvent
        from datetime import datetime, timedelta

        # Mock classify_case to return upset_bid
        mock_classify.return_value = 'upset_bid'

        # Track thread creations
        thread_targets = []
        def capture_thread(*args, **kwargs):
            thread_targets.append((kwargs.get('target'), kwargs.get('args')))
            t = mock.MagicMock()
            return t
        mock_thread.side_effect = capture_thread

        # test_case_upcoming fixture returns the case_id
        case_id = test_case_upcoming

        # Add a sale event to trigger upset_bid classification
        with get_session() as session:
            sale_event = CaseEvent(
                case_id=case_id,
                event_date=datetime.now().date(),
                event_description="Report of Foreclosure Sale filed"
            )
            session.add(sale_event)
            session.commit()

        # Run classification
        update_case_classification(case_id)

        # Verify that both enrichment and vision threads were created
        # Should have 2 threads: enrichment + vision
        assert len(thread_targets) == 2, f"Expected 2 threads, got {len(thread_targets)}"

        # Check that the correct functions are being passed as targets
        enrichment_found = False
        vision_found = False

        for target, args in thread_targets:
            if target == _trigger_enrichment_async:
                enrichment_found = True
                assert args[0] == case_id, "Enrichment trigger called with wrong case_id"
            elif target == _trigger_vision_extraction_async:
                vision_found = True
                assert args[0] == case_id, "Vision trigger called with wrong case_id"

        assert enrichment_found, "Enrichment trigger not scheduled"
        assert vision_found, "Vision extraction trigger not scheduled"


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
    from database.models import Case, CaseEvent
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
        case_id = case.id

    yield case_id

    # Cleanup
    with get_session() as session:
        # Clean up events first
        session.query(CaseEvent).filter_by(case_id=case_id).delete()
        session.query(Case).filter_by(id=case_id).delete()
        session.commit()
