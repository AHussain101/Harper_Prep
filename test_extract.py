"""
Test suite for Phase 1: Contextual Extraction
Tests schema validation, extraction logic, and integration with OpenAI API
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock

from extract import (
    Address,
    BusinessEntity,
    IndustryClassification,
    RevenueDetails,
    RiskFactors,
    InsuranceHistory,
    SocialContext,
    DiscoveryCallExtraction,
    extract_from_transcript,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_transcript():
    """Load the actual transcript.txt for testing"""
    with open("transcript.txt", "r") as f:
        return f.read()


@pytest.fixture
def minimal_transcript():
    """Minimal transcript for quick tests"""
    return """
    Broker: What's the business name?
    Client: It's called "Test Bar" at 123 Main St, Austin, Texas 78701.
    Broker: Are you leasing?
    Client: Yes, leasing.
    """


@pytest.fixture
def mock_extraction_response():
    """Mock response that matches expected schema"""
    return DiscoveryCallExtraction(
        business_entity=BusinessEntity(
            legal_name=None,
            dba="The Rusty Anchor",
            address=Address(
                street="450 Maple Avenue",
                city="Charleston",
                state="South Carolina",
                zip_code="29401"
            ),
            occupancy_type="Leasing"
        ),
        industry_classification=IndustryClassification(
            naics_code="722410",
            sic_code="5813",
            business_description="Tavern focusing on high-end cocktails with piano entertainment"
        ),
        revenue_details=RevenueDetails(
            gross_annual_sales=850000.0,
            alcohol_percentage=70.0,
            food_percentage=30.0
        ),
        risk_factors=RiskFactors(
            hazards=["live entertainment", "alcohol service"],
            operating_hours=None,
            special_features=["high-end cocktails"]
        ),
        insurance_history=InsuranceHistory(
            past_carrier="Geico",
            past_carrier_context="personal",
            current_need="specialized business policy",
            urgency="ASAP"
        ),
        social_context=SocialContext(
            availability_notes="Unavailable until 1:00 PM Tuesday",
            preferred_contact_time="Tuesday afternoon",
            personal_constraints="daughter's dentist appointment",
            contact_restrictions="Don't call tomorrow morning"
        )
    )


# =============================================================================
# UNIT TESTS: SCHEMA VALIDATION
# =============================================================================

class TestAddressSchema:
    """Tests for Address Pydantic model"""

    def test_valid_address(self):
        addr = Address(
            street="450 Maple Avenue",
            city="Charleston",
            state="South Carolina",
            zip_code="29401"
        )
        assert addr.street == "450 Maple Avenue"
        assert addr.city == "Charleston"
        assert addr.state == "South Carolina"
        assert addr.zip_code == "29401"

    def test_partial_address(self):
        """Address with missing fields should use None defaults"""
        addr = Address(city="Charleston")
        assert addr.street is None
        assert addr.city == "Charleston"
        assert addr.state is None
        assert addr.zip_code is None

    def test_empty_address(self):
        """Empty address should be valid with all None"""
        addr = Address()
        assert addr.street is None
        assert addr.city is None


class TestBusinessEntitySchema:
    """Tests for BusinessEntity Pydantic model"""

    def test_valid_business_entity(self):
        entity = BusinessEntity(
            legal_name="Rusty Anchor LLC",
            dba="The Rusty Anchor",
            address=Address(street="450 Maple Avenue", city="Charleston"),
            occupancy_type="Leasing"
        )
        assert entity.legal_name == "Rusty Anchor LLC"
        assert entity.dba == "The Rusty Anchor"
        assert entity.occupancy_type == "Leasing"

    def test_dba_only(self):
        """Business with DBA but no legal name (common case)"""
        entity = BusinessEntity(dba="The Rusty Anchor")
        assert entity.legal_name is None
        assert entity.dba == "The Rusty Anchor"


class TestInsuranceHistorySchema:
    """Tests for InsuranceHistory - Critical for context differentiation"""

    def test_context_differentiation(self):
        """PRD Requirement: past_carrier must be separate from current_need"""
        history = InsuranceHistory(
            past_carrier="Geico",
            past_carrier_context="personal",
            current_need="specialized business policy",
            urgency="ASAP"
        )
        # These MUST be distinct fields per PRD
        assert history.past_carrier == "Geico"
        assert history.past_carrier_context == "personal"
        assert history.current_need == "specialized business policy"
        # Verify they are independent
        assert history.past_carrier != history.current_need

    def test_no_past_carrier(self):
        """Client with no previous insurance"""
        history = InsuranceHistory(current_need="general liability")
        assert history.past_carrier is None
        assert history.current_need == "general liability"


class TestSocialContextSchema:
    """Tests for SocialContext (The Harper Touch)"""

    def test_harper_touch_fields(self):
        """PRD Requirement: Non-business constraints captured separately"""
        social = SocialContext(
            availability_notes="Unavailable until 1:00 PM Tuesday",
            preferred_contact_time="Tuesday afternoon",
            personal_constraints="daughter's dentist appointment",
            contact_restrictions="Don't call tomorrow morning"
        )
        assert social.availability_notes is not None
        assert social.personal_constraints is not None
        assert "dentist" in social.personal_constraints

    def test_empty_social_context(self):
        """Client with no scheduling constraints"""
        social = SocialContext()
        assert social.availability_notes is None
        assert social.preferred_contact_time is None


class TestRiskFactorsSchema:
    """Tests for RiskFactors model"""

    def test_multiple_hazards(self):
        risk = RiskFactors(
            hazards=["live entertainment", "deep fryer", "late hours"],
            operating_hours="11 PM - 2 AM",
            special_features=["rooftop bar"]
        )
        assert len(risk.hazards) == 3
        assert "live entertainment" in risk.hazards

    def test_empty_hazards(self):
        """Low-risk business with no hazards"""
        risk = RiskFactors(hazards=[])
        assert risk.hazards == []


class TestDiscoveryCallExtractionSchema:
    """Tests for the complete extraction schema"""

    def test_full_extraction_serialization(self, mock_extraction_response):
        """Test that complete extraction serializes to JSON correctly"""
        json_output = mock_extraction_response.model_dump_json()
        parsed = json.loads(json_output)

        assert parsed["business_entity"]["dba"] == "The Rusty Anchor"
        assert parsed["insurance_history"]["past_carrier"] == "Geico"
        assert parsed["insurance_history"]["current_need"] == "specialized business policy"
        assert parsed["social_context"]["availability_notes"] is not None

    def test_null_fields_not_hallucinated(self, mock_extraction_response):
        """PRD Requirement: Missing fields must be null, not hallucinated"""
        data = mock_extraction_response.model_dump()
        # legal_name was not in transcript, should be None
        assert data["business_entity"]["legal_name"] is None


# =============================================================================
# UNIT TESTS: MOCKED EXTRACTION
# =============================================================================

class TestExtractFromTranscriptMocked:
    """Tests with mocked OpenAI API calls"""

    @patch("extract.instructor")
    @patch("extract.openai")
    def test_extraction_calls_api(self, mock_openai, mock_instructor, minimal_transcript, mock_extraction_response):
        """Verify extraction function calls the API correctly"""
        # Setup mock
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_extraction_response

        # Call function
        result = extract_from_transcript(minimal_transcript)

        # Verify API was called
        mock_instructor.from_openai.assert_called_once()
        mock_client.chat.completions.create.assert_called_once()

        # Verify result
        assert result.business_entity.dba == "The Rusty Anchor"

    @patch("extract.instructor")
    @patch("extract.openai")
    def test_extraction_uses_correct_model(self, mock_openai, mock_instructor, minimal_transcript, mock_extraction_response):
        """Verify gpt-4o model is used"""
        mock_client = MagicMock()
        mock_instructor.from_openai.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_extraction_response

        extract_from_transcript(minimal_transcript)

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"


# =============================================================================
# INTEGRATION TESTS: REAL API
# =============================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping integration tests"
)
class TestIntegrationWithAPI:
    """Integration tests that call the real OpenAI API"""

    def test_full_extraction_from_transcript(self, sample_transcript):
        """End-to-end test with real transcript"""
        result = extract_from_transcript(sample_transcript)

        # Business Details
        assert result.business_entity.dba == "The Rusty Anchor"
        assert result.business_entity.address.street == "450 Maple Avenue"
        assert result.business_entity.address.city == "Charleston"
        assert result.business_entity.address.state in ["South Carolina", "SC"]
        assert result.business_entity.address.zip_code == "29401"
        assert result.business_entity.occupancy_type.lower() == "leasing"

        # Revenue
        assert result.revenue_details.gross_annual_sales == 850000.0
        assert result.revenue_details.alcohol_percentage == 70.0
        assert result.revenue_details.food_percentage == 30.0

    def test_context_differentiation_integration(self, sample_transcript):
        """PRD Critical: past_carrier vs current_need correctly separated"""
        result = extract_from_transcript(sample_transcript)

        # Past carrier was Geico for PERSONAL insurance
        assert result.insurance_history.past_carrier == "Geico"
        assert "personal" in result.insurance_history.past_carrier_context.lower()

        # Current need is BUSINESS policy - must be different
        assert "business" in result.insurance_history.current_need.lower() or \
               "specialized" in result.insurance_history.current_need.lower()

    def test_harper_touch_integration(self, sample_transcript):
        """PRD Critical: Social context extracted correctly"""
        result = extract_from_transcript(sample_transcript)

        # Client has scheduling constraints
        assert result.social_context.availability_notes is not None
        assert "tuesday" in result.social_context.availability_notes.lower() or \
               "1:00" in result.social_context.availability_notes.lower()

        # Personal constraint mentioned
        assert result.social_context.personal_constraints is not None
        assert "dentist" in result.social_context.personal_constraints.lower() or \
               "daughter" in result.social_context.personal_constraints.lower()

    def test_risk_factors_integration(self, sample_transcript):
        """Verify risk factors are extracted"""
        result = extract_from_transcript(sample_transcript)

        # Should identify entertainment risk
        hazards_lower = [h.lower() for h in result.risk_factors.hazards]
        has_entertainment_risk = any(
            "piano" in h or "entertainment" in h or "music" in h
            for h in hazards_lower
        )
        assert has_entertainment_risk, f"Expected entertainment risk in {result.risk_factors.hazards}"

    def test_industry_classification_integration(self, sample_transcript):
        """Verify NAICS code is correct for bar/tavern"""
        result = extract_from_transcript(sample_transcript)

        # NAICS 722410 = Drinking Places (Alcoholic Beverages)
        assert result.industry_classification.naics_code == "722410"

    def test_no_hallucination_integration(self, sample_transcript):
        """PRD Critical: Fields not in transcript must be null"""
        result = extract_from_transcript(sample_transcript)

        # Legal name was never mentioned - must be null
        assert result.business_entity.legal_name is None

        # Operating hours not specified
        assert result.risk_factors.operating_hours is None


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may call external APIs)"
    )
