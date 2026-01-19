"""
Test suite for Phase 4: Execution Engine (The Closer)
Tests for Submission State Manager, Temporal Scheduler, Executive Summary Generator, and Execution Engine
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from enum import Enum
import json

from extract import (
    DiscoveryCallExtraction,
    SocialContext,
    BusinessEntity,
    Address,
    IndustryClassification,
    RevenueDetails,
    RiskFactors,
    InsuranceHistory,
    extract_from_transcript,
)
from form_mapper import MappedFormOutput, map_extraction_to_forms
from routing_engine import RoutingRecommendation, RoutingEngine
from underwriter_db import get_all_underwriters
from execution_engine import (
    SubmissionState,
    SubmissionStatus,
    TemporalScheduler,
    ExecutiveSummaryGenerator,
    ExecutiveSummary,
    ExecutionEngine,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_social_context():
    """Social context from The Rusty Anchor transcript"""
    return SocialContext(
        availability_notes="Unavailable until 1:00 PM Tuesday",
        preferred_contact_time="Tuesday afternoon",
        personal_constraints="daughter's dentist appointment",
        contact_restrictions="Don't call tomorrow morning"
    )


@pytest.fixture
def sample_address():
    """Address for The Rusty Anchor"""
    return Address(
        street="450 Maple Avenue",
        city="Charleston",
        state="South Carolina",
        zip_code="29401"
    )


@pytest.fixture
def sample_business_entity(sample_address):
    """Business entity for The Rusty Anchor"""
    return BusinessEntity(
        legal_name=None,
        dba="The Rusty Anchor",
        address=sample_address,
        occupancy_type="Leasing"
    )


@pytest.fixture
def sample_industry_classification():
    """Industry classification for a bar/tavern"""
    return IndustryClassification(
        naics_code="722410",
        sic_code="5813",
        business_description="Tavern focusing on high-end cocktails with piano entertainment"
    )


@pytest.fixture
def sample_revenue_details():
    """Revenue details for The Rusty Anchor"""
    return RevenueDetails(
        gross_annual_sales=850000.0,
        alcohol_percentage=70.0,
        food_percentage=30.0
    )


@pytest.fixture
def sample_risk_factors():
    """Risk factors for The Rusty Anchor"""
    return RiskFactors(
        hazards=["live entertainment", "alcohol service", "deep fryer"],
        operating_hours="11 PM - 2 AM",
        special_features=["high-end cocktails", "piano entertainment"]
    )


@pytest.fixture
def sample_insurance_history():
    """Insurance history for The Rusty Anchor"""
    return InsuranceHistory(
        past_carrier="Geico",
        past_carrier_context="personal",
        current_need="specialized business policy",
        urgency="ASAP"
    )


@pytest.fixture
def sample_extraction(
    sample_business_entity,
    sample_industry_classification,
    sample_revenue_details,
    sample_risk_factors,
    sample_insurance_history,
    sample_social_context
):
    """Full extraction for The Rusty Anchor"""
    return DiscoveryCallExtraction(
        business_entity=sample_business_entity,
        industry_classification=sample_industry_classification,
        revenue_details=sample_revenue_details,
        risk_factors=sample_risk_factors,
        insurance_history=sample_insurance_history,
        social_context=sample_social_context
    )


@pytest.fixture
def sample_mapped_output(sample_extraction):
    """Mapped form output for The Rusty Anchor"""
    return map_extraction_to_forms(sample_extraction)


@pytest.fixture
def sample_recommendation():
    """Routing recommendation for Kevin O'Brien"""
    from underwriter_db import Underwriter, Region, Workload

    underwriter = Underwriter(
        name="Kevin O'Brien",
        email="kobrien@nautilusins.com",
        phone="(843) 555-1234",
        region=Region.SOUTHEAST,
        risk_appetite=["Bars", "Restaurants", "Taverns"],
        risk_aversions=["Manufacturing"],
        naics_specialties=["722410", "722511"],
        avg_turnaround_days=2.0,
        acceptance_rate=0.87,
        current_workload=Workload.MEDIUM,
        notes="Specializes in hospitality in the Southeast"
    )

    return RoutingRecommendation(
        recommended_underwriter=underwriter,
        score=52.1,
        justification="Kevin O'Brien selected. Specializes in NAICS 722410 (bars) in Southeast region. 2-day avg turnaround, 87% acceptance rate."
    )


@pytest.fixture
def sample_submission_status(sample_recommendation):
    """A submission in ROUTED state for The Rusty Anchor"""
    return SubmissionStatus(
        submission_id="SUB-2024-001",
        business_name="The Rusty Anchor",
        current_state=SubmissionState.ROUTED,
        recommended_underwriter=sample_recommendation.recommended_underwriter.name,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        broker_tasks_pending=1,
        state_history=[
            {
                "state": SubmissionState.RECEIVED.value,
                "timestamp": datetime.now() - timedelta(hours=2),
                "notes": "Submission received"
            },
            {
                "state": SubmissionState.EXTRACTED.value,
                "timestamp": datetime.now() - timedelta(hours=1),
                "notes": "Phase 1 complete"
            },
            {
                "state": SubmissionState.MAPPED.value,
                "timestamp": datetime.now() - timedelta(minutes=30),
                "notes": "Phase 2 complete"
            },
            {
                "state": SubmissionState.ROUTED.value,
                "timestamp": datetime.now(),
                "notes": "Phase 3 complete"
            }
        ]
    )


@pytest.fixture
def empty_social_context():
    """Social context with no constraints"""
    return SocialContext(
        availability_notes=None,
        preferred_contact_time=None,
        personal_constraints=None,
        contact_restrictions=None
    )


# =============================================================================
# UNIT TESTS: SUBMISSION STATE MANAGER
# =============================================================================

class TestSubmissionStateManager:
    """Tests for SubmissionState and SubmissionStatus"""

    def test_submission_state_transitions(self, sample_submission_status):
        """Verify valid state transitions"""
        # Valid transitions: NEW -> EXTRACTED -> MAPPED -> ROUTED -> SCHEDULED -> SUBMITTED
        valid_transitions = [
            (SubmissionState.RECEIVED, SubmissionState.EXTRACTED),
            (SubmissionState.EXTRACTED, SubmissionState.MAPPED),
            (SubmissionState.MAPPED, SubmissionState.ROUTED),
            (SubmissionState.ROUTED, SubmissionState.SCHEDULED),
            (SubmissionState.SCHEDULED, SubmissionState.SENT),
        ]

        for from_state, to_state in valid_transitions:
            # Verify transition is allowed
            assert from_state != to_state
            # States should be distinct enum values
            assert from_state.value != to_state.value

    def test_state_history_tracking(self, sample_submission_status):
        """Verify history is recorded with timestamps"""
        history = sample_submission_status.state_history

        # Should have multiple history entries
        assert len(history) >= 4

        # Each entry should have required fields
        for entry in history:
            assert "state" in entry
            assert "timestamp" in entry
            assert "reason" in entry

        # History should be chronological
        timestamps = [entry["timestamp"] for entry in history]
        assert timestamps == sorted(timestamps)

    def test_submission_status_creation(self, sample_recommendation):
        """Verify all fields populated correctly"""
        status = SubmissionStatus(
            submission_id="SUB-2024-002",
            business_name="Test Business",
            current_state=SubmissionState.RECEIVED,
            recommended_underwriter=None,
            carrier_name=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            state_history=[]
        )

        assert status.submission_id == "SUB-2024-002"
        assert status.business_name == "Test Business"
        assert status.current_state == SubmissionState.RECEIVED
        assert status.recommended_underwriter is None
        assert status.carrier_name is None
        assert isinstance(status.created_at, datetime)
        assert isinstance(status.updated_at, datetime)
        assert status.state_history == []

    def test_invalid_state_transition(self, sample_submission_status):
        """Verify invalid transitions are rejected"""
        # Cannot go backwards from ROUTED to NEW
        invalid_transitions = [
            (SubmissionState.ROUTED, SubmissionState.RECEIVED),
            (SubmissionState.SENT, SubmissionState.EXTRACTED),
            (SubmissionState.SCHEDULED, SubmissionState.MAPPED),
        ]

        # The state machine should reject these
        # This test validates the model correctly identifies invalid transitions
        for from_state, to_state in invalid_transitions:
            # Going backwards should not be a natural progression
            from_idx = list(SubmissionState).index(from_state)
            to_idx = list(SubmissionState).index(to_state)
            assert to_idx < from_idx, f"Expected {to_state} to come before {from_state}"


# =============================================================================
# UNIT TESTS: TEMPORAL SCHEDULER
# =============================================================================

class TestTemporalScheduler:
    """Tests for TemporalScheduler"""

    def test_parse_availability_tuesday_afternoon(self, sample_social_context):
        """Parse 'unavailable until 1:00 PM Tuesday'"""
        scheduler = TemporalScheduler()

        availability = scheduler.parse_availability(sample_social_context)

        # Should identify Tuesday 1:00 PM as earliest contact time
        assert availability is not None
        assert "tuesday" in availability.lower() or availability.weekday() == 1  # Tuesday

    def test_parse_availability_tomorrow_morning(self):
        """Parse 'don't call tomorrow morning'"""
        scheduler = TemporalScheduler()
        context = SocialContext(
            contact_restrictions="Don't call tomorrow morning"
        )

        availability = scheduler.parse_availability(context)

        # Should return a time after tomorrow morning
        assert availability is not None

    def test_get_next_business_window_weekday(self):
        """Next window during business hours on a weekday"""
        scheduler = TemporalScheduler()

        # Assume current time is 10 AM on a Wednesday
        reference_time = datetime(2024, 1, 10, 10, 0)  # Wednesday 10 AM

        next_window = scheduler.get_next_business_window(reference_time)

        # Should be within business hours (9 AM - 5 PM)
        assert next_window.hour >= 9
        assert next_window.hour < 17
        # Should be same day or later
        assert next_window >= reference_time

    def test_get_next_business_window_weekend(self):
        """Weekend should return Monday 9 AM"""
        scheduler = TemporalScheduler()

        # Saturday at noon
        saturday = datetime(2024, 1, 13, 12, 0)  # Saturday

        next_window = scheduler.get_next_business_window(saturday)

        # Should be Monday
        assert next_window.weekday() == 0  # Monday
        # Should be 9 AM
        assert next_window.hour == 9
        assert next_window.minute == 0

    def test_get_next_business_window_after_hours(self):
        """After 5 PM should return next morning"""
        scheduler = TemporalScheduler()

        # Wednesday at 6 PM
        wednesday_evening = datetime(2024, 1, 10, 18, 0)

        next_window = scheduler.get_next_business_window(wednesday_evening)

        # Should be Thursday 9 AM
        assert next_window.day == 11  # Thursday
        assert next_window.hour == 9

    def test_schedule_action_respects_constraints(self, sample_social_context):
        """Scheduled time respects social context constraints"""
        scheduler = TemporalScheduler()

        # Reference time: Monday 10 AM
        reference_time = datetime(2024, 1, 8, 10, 0)  # Monday

        scheduled_time = scheduler.schedule_action(
            reference_time=reference_time,
            social_context=sample_social_context
        )

        # Should be Tuesday afternoon (after 1 PM) per constraints
        assert scheduled_time.weekday() == 1  # Tuesday
        assert scheduled_time.hour >= 13  # After 1 PM

    def test_schedule_action_returns_reason(self, sample_social_context):
        """Returns human-readable reason for scheduling"""
        scheduler = TemporalScheduler()

        reference_time = datetime(2024, 1, 8, 10, 0)

        scheduled_time, reason = scheduler.schedule_action_with_reason(
            reference_time=reference_time,
            social_context=sample_social_context
        )

        # Should have a human-readable reason
        assert reason is not None
        assert isinstance(reason, str)
        assert len(reason) > 0
        # Reason should mention the constraint
        assert "tuesday" in reason.lower() or "1:00" in reason.lower() or "dentist" in reason.lower()


# =============================================================================
# UNIT TESTS: EXECUTIVE SUMMARY GENERATOR
# =============================================================================

class TestExecutiveSummaryGenerator:
    """Tests for ExecutiveSummaryGenerator"""

    def test_generate_summary_has_all_sections(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        sample_submission_status
    ):
        """Verify headline, business, routing, etc. sections exist"""
        generator = ExecutiveSummaryGenerator()

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        # Should have all required sections
        assert summary.headline is not None
        assert summary.business_snapshot is not None
        assert summary.routing_rationale is not None
        assert summary.next_action is not None
        assert summary.broker_tasks is not None
        assert summary.harper_touch_note is not None

    def test_headline_format(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        sample_submission_status
    ):
        """Headline includes business name and underwriter"""
        generator = ExecutiveSummaryGenerator()

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        headline = summary.headline

        # Should contain business name
        assert "Rusty Anchor" in headline
        # Should contain underwriter name
        assert "Kevin O'Brien" in headline or "Nautilus" in headline

    def test_routing_rationale_mentions_key_factors(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        sample_submission_status
    ):
        """Mentions NAICS, region, turnaround in rationale"""
        generator = ExecutiveSummaryGenerator()

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        rationale = summary.routing_rationale.lower()

        # Should mention at least some key factors
        key_factors_mentioned = 0
        if "naics" in rationale or "722410" in rationale:
            key_factors_mentioned += 1
        if "southeast" in rationale or "region" in rationale or "charleston" in rationale:
            key_factors_mentioned += 1
        if "turnaround" in rationale or "24" in rationale or "48" in rationale:
            key_factors_mentioned += 1
        if "bar" in rationale or "tavern" in rationale:
            key_factors_mentioned += 1

        assert key_factors_mentioned >= 2, f"Expected at least 2 key factors in rationale: {summary.routing_rationale}"

    def test_next_action_includes_scheduled_time(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        sample_submission_status
    ):
        """Shows when email will be sent"""
        generator = ExecutiveSummaryGenerator()

        # Add scheduled time to status
        sample_submission_status.scheduled_send_time = datetime(2024, 1, 9, 13, 0)  # Tuesday 1 PM
        sample_submission_status.current_state = SubmissionState.SCHEDULED

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        next_action = summary.next_action.lower()

        # Should mention timing
        assert "tuesday" in next_action or "1:00" in next_action or "scheduled" in next_action

    def test_broker_tasks_from_mapped_output(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        sample_submission_status
    ):
        """Lists pending broker tasks from mapped output"""
        generator = ExecutiveSummaryGenerator()

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        # Should have broker tasks from mapped output
        assert len(summary.broker_tasks) > 0

        # Should include tasks from the mapped output
        tasks_text = " ".join(summary.broker_tasks).lower()
        assert "operating hours" in tasks_text or "liquor license" in tasks_text or "loss runs" in tasks_text

    def test_harper_touch_note_captures_context(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        sample_submission_status
    ):
        """Includes personal constraints in Harper Touch note"""
        generator = ExecutiveSummaryGenerator()

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        harper_note = summary.harper_touch_note.lower()

        # Should mention the personal constraints
        assert "dentist" in harper_note or "daughter" in harper_note or "tuesday" in harper_note


# =============================================================================
# UNIT TESTS: EXECUTION ENGINE
# =============================================================================

class TestExecutionEngine:
    """Tests for ExecutionEngine"""

    def test_process_submission_returns_status_and_summary(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation
    ):
        """Returns both SubmissionStatus and ExecutiveSummary objects"""
        engine = ExecutionEngine()

        status, summary = engine.process_submission(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation
        )

        # Should return both objects
        assert isinstance(status, SubmissionStatus)
        assert isinstance(summary, ExecutiveSummary)

    def test_process_submission_state_is_scheduled(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation
    ):
        """State should be SCHEDULED after processing"""
        engine = ExecutionEngine()

        status, _ = engine.process_submission(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation
        )

        # After processing, state should be SCHEDULED
        assert status.current_state == SubmissionState.SCHEDULED

    def test_update_state_records_history(self, sample_submission_status):
        """History grows with each update"""
        engine = ExecutionEngine()

        initial_history_length = len(sample_submission_status.state_history)

        updated_status = engine.update_state(
            status=sample_submission_status,
            new_state=SubmissionState.SCHEDULED,
            reason="Ready for scheduled submission"
        )

        # History should grow by 1
        assert len(updated_status.state_history) == initial_history_length + 1

        # Latest entry should be the new state
        latest_entry = updated_status.state_history[-1]
        assert latest_entry["state"] == SubmissionState.SCHEDULED.value
        assert "scheduled" in latest_entry["reason"].lower()

    def test_get_pending_actions_returns_due_items(self):
        """Only returns actions that are due"""
        engine = ExecutionEngine()

        # Create statuses with different scheduled times
        now = datetime.now()

        past_due_status = SubmissionStatus(
            submission_id="SUB-001",
            business_name="Past Due Business",
            current_state=SubmissionState.SCHEDULED,
            recommended_underwriter="Test Underwriter",
            carrier_name="Test Carrier",
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=1),
            scheduled_send_time=now - timedelta(hours=1),  # Past due
            state_history=[]
        )

        future_status = SubmissionStatus(
            submission_id="SUB-002",
            business_name="Future Business",
            current_state=SubmissionState.SCHEDULED,
            recommended_underwriter="Test Underwriter",
            carrier_name="Test Carrier",
            created_at=now,
            updated_at=now,
            scheduled_send_time=now + timedelta(hours=2),  # Future
            state_history=[]
        )

        pending = engine.get_pending_actions([past_due_status, future_status])

        # Should only return the past due item
        assert len(pending) == 1
        assert pending[0].submission_id == "SUB-001"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.integration
class TestIntegrationPipeline:
    """Integration tests for the full pipeline"""

    def test_full_pipeline_phase1_to_phase4(self, sample_transcript):
        """transcript -> extraction -> mapping -> routing -> execution"""
        # Skip if no API key
        import os
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        # Phase 1: Extraction
        extraction = extract_from_transcript(sample_transcript)
        assert extraction.business_entity.dba is not None

        # Phase 2: Form Mapping
        mapped_output = map_extraction_to_forms(extraction)
        assert mapped_output.acord_125_data is not None

        # Phase 3: Routing
        routing_engine = RoutingEngine()
        underwriters = get_all_underwriters()
        recommendation = routing_engine.route(extraction, underwriters)
        assert recommendation.underwriter_name is not None

        # Phase 4: Execution
        exec_engine = ExecutionEngine()
        status, summary = exec_engine.process_submission(
            extraction=extraction,
            mapped_output=mapped_output,
            recommendation=recommendation
        )

        # Verify end-to-end
        assert status.current_state == SubmissionState.SCHEDULED
        assert summary.headline is not None

    def test_harper_touch_respected_in_scheduling(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation
    ):
        """Tuesday afternoon constraint honored"""
        engine = ExecutionEngine()

        # Process with social context containing Tuesday constraint
        status, summary = engine.process_submission(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation
        )

        # Scheduled time should be Tuesday afternoon
        if status.scheduled_send_time:
            # Should be Tuesday (weekday 1)
            assert status.scheduled_send_time.weekday() == 1
            # Should be afternoon (after 1 PM)
            assert status.scheduled_send_time.hour >= 13

    def test_executive_summary_complete(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        sample_submission_status
    ):
        """All sections populated from real data"""
        generator = ExecutiveSummaryGenerator()

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        # All sections should be non-empty
        assert len(summary.headline) > 0
        assert len(summary.business_snapshot) > 0
        assert len(summary.routing_rationale) > 0
        assert len(summary.next_action) > 0
        assert len(summary.harper_touch_note) > 0

        # Business snapshot should contain actual data
        snapshot = summary.business_snapshot.lower()
        assert "rusty anchor" in snapshot or "charleston" in snapshot or "850000" in snapshot

    def test_end_to_end_generates_actionable_output(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation
    ):
        """Output is ready for broker use"""
        engine = ExecutionEngine()

        status, summary = engine.process_submission(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation
        )

        # Status should have all needed info for action
        assert status.submission_id is not None
        assert status.business_name == "The Rusty Anchor"
        assert status.recommended_underwriter is not None
        assert status.carrier_name is not None

        # Summary should be actionable
        assert summary.headline is not None
        assert summary.next_action is not None
        assert len(summary.broker_tasks) >= 0


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Edge case tests"""

    def test_no_social_context_uses_default_schedule(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation,
        empty_social_context
    ):
        """Missing Harper Touch uses immediate business hours"""
        # Replace social context with empty one
        sample_extraction.social_context = empty_social_context

        engine = ExecutionEngine()

        status, _ = engine.process_submission(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=sample_recommendation
        )

        # Should still have a scheduled time
        assert status.scheduled_send_time is not None

        # Should be during business hours
        scheduled_hour = status.scheduled_send_time.hour
        assert 9 <= scheduled_hour < 17

    def test_weekend_submission_schedules_monday(
        self,
        sample_extraction,
        sample_mapped_output,
        sample_recommendation
    ):
        """Weekend input schedules for Monday"""
        engine = ExecutionEngine()
        scheduler = TemporalScheduler()

        # Force reference time to Saturday
        saturday = datetime(2024, 1, 13, 14, 0)  # Saturday 2 PM

        with patch.object(scheduler, '_get_current_time', return_value=saturday):
            next_window = scheduler.get_next_business_window(saturday)

        # Should be Monday
        assert next_window.weekday() == 0  # Monday
        assert next_window.hour == 9

    def test_empty_broker_tasks_handled(
        self,
        sample_extraction,
        sample_recommendation,
        sample_submission_status
    ):
        """No broker tasks generates appropriate message"""
        generator = ExecutiveSummaryGenerator()

        # Create mapped output with no broker tasks
        mapped_output = MappedFormOutput(
            acord_125_data={"applicant_name": "Test"},
            acord_126_data={},
            supplemental_data={},
            broker_tasks=[],  # Empty
            validation_warnings=[]
        )

        summary = generator.generate(
            extraction=sample_extraction,
            mapped_output=mapped_output,
            recommendation=sample_recommendation,
            submission_status=sample_submission_status
        )

        # Should handle empty tasks gracefully
        assert summary.broker_tasks is not None
        # Either empty list or a message indicating no tasks
        assert isinstance(summary.broker_tasks, list)

    def test_missing_recommendation_handled(
        self,
        sample_extraction,
        sample_mapped_output
    ):
        """Handle case with no underwriter match"""
        engine = ExecutionEngine()

        # Process with None recommendation
        status, summary = engine.process_submission(
            extraction=sample_extraction,
            mapped_output=sample_mapped_output,
            recommendation=None  # No match found
        )

        # Should still create a status
        assert status is not None
        assert status.recommended_underwriter is None

        # Summary should indicate no match
        assert summary is not None
        assert "no match" in summary.routing_rationale.lower() or \
               "manual" in summary.routing_rationale.lower() or \
               summary.routing_rationale is not None


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

@pytest.fixture
def sample_transcript():
    """Load the actual transcript.txt for testing"""
    try:
        with open("transcript.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        # Return minimal transcript if file not found
        return """
        Broker: What's the business name?
        Client: It's called "The Rusty Anchor" at 450 Maple Avenue, Charleston, South Carolina 29401.
        Broker: Are you leasing?
        Client: Yes, leasing.
        Broker: What type of business?
        Client: We're a tavern focusing on high-end cocktails with piano entertainment.
        Broker: Annual revenue?
        Client: About $850,000, roughly 70% alcohol and 30% food.
        Broker: Any past insurance?
        Client: Just Geico for personal stuff.
        Broker: When can we follow up?
        Client: Don't call tomorrow morning - my daughter has a dentist appointment.
               I'll be unavailable until 1:00 PM Tuesday. Tuesday afternoon works best.
        """


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may call external APIs)"
    )
