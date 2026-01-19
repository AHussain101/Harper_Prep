"""
Test suite for Phase 3: Intelligent Underwriter Routing
Tests underwriter database, risk profile extraction, and routing engine scoring logic.

The Computational Broker Engine - Phase 3 Tests
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import List

# Phase 1 imports
from extract import (
    DiscoveryCallExtraction,
    BusinessEntity,
    Address,
    IndustryClassification,
    RevenueDetails,
    RiskFactors,
    InsuranceHistory,
    SocialContext,
    extract_from_transcript,
)

# Phase 2 imports
from form_mapper import (
    MappedFormOutput,
    Accord125_Form,
    Accord126_Form,
    Accord125_ApplicantInfo,
    Accord125_PremisesInfo,
    Accord125_BusinessInfo,
    Accord125_RevenueInfo,
    Accord126_LiquorLiability,
    Accord126_EntertainmentExposure,
    Accord126_OperationsHazards,
    BrokerTaskList,
    PremisesOccupancy,
    LiquorLiabilityType,
    map_extraction_to_forms,
)

# Phase 3 imports (modules to be implemented)
from underwriter_db import (
    Underwriter,
    get_all_underwriters,
    get_underwriters_by_region,
    get_underwriters_by_naics,
)

from routing_engine import (
    RoutingEngine,
    RiskProfile,
    UnderwriterRecommendation,
    RoutingResult,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_mapped_output():
    """
    A MappedFormOutput for "The Rusty Anchor" bar in Charleston, SC.
    This represents a typical bar/tavern with live entertainment.
    """
    # Create Accord 125 form
    accord_125 = Accord125_Form()
    accord_125.applicant.applicant_name = None
    accord_125.applicant.dba = "The Rusty Anchor"
    accord_125.applicant.mailing_address = "450 Maple Avenue"
    accord_125.applicant.mailing_city = "Charleston"
    accord_125.applicant.mailing_state = "South Carolina"
    accord_125.applicant.mailing_zip = "29401"

    accord_125.premises.street_address = "450 Maple Avenue"
    accord_125.premises.city = "Charleston"
    accord_125.premises.state = "South Carolina"
    accord_125.premises.zip_code = "29401"
    accord_125.premises.occupancy = PremisesOccupancy.TENANT

    accord_125.business.nature_of_business = "Tavern focusing on high-end cocktails with piano entertainment"
    accord_125.business.naics_code = "722410"
    accord_125.business.sic_code = "5813"

    accord_125.revenue.annual_gross_sales = 850000.0

    # Create Accord 126 form
    accord_126 = Accord126_Form()
    accord_126.classification.class_code = "722410"
    accord_126.classification.classification_description = "Tavern focusing on high-end cocktails with piano entertainment"

    accord_126.liquor_liability.liquor_liability_required = True
    accord_126.liquor_liability.liquor_liability_type = LiquorLiabilityType.SELL
    accord_126.liquor_liability.alcohol_sales_percentage = 70.0
    accord_126.liquor_liability.food_sales_percentage = 30.0
    accord_126.liquor_liability.annual_liquor_receipts = 595000.0

    accord_126.entertainment.live_entertainment = True
    accord_126.entertainment.entertainment_description = "piano entertainment"

    accord_126.hazards.hazards = ["live entertainment", "alcohol service", "piano player"]

    # Create complete mapped output
    mapped_output = MappedFormOutput(
        accord_125=accord_125,
        accord_126=accord_126,
        broker_tasks=BrokerTaskList(),
        mapping_summary={
            "accord_125": {"populated_fields": 15, "total_fields": 25, "completion_percentage": 60.0},
            "accord_126": {"populated_fields": 10, "total_fields": 20, "completion_percentage": 50.0},
            "broker_tasks_count": 1,
        }
    )

    return mapped_output


@pytest.fixture
def sample_underwriter():
    """
    An underwriter who specializes in bars in the Southeast region.
    This is the ideal match for The Rusty Anchor in Charleston, SC.
    """
    return Underwriter(
        id="UW001",
        name="Sarah Mitchell",
        company="Southeast Hospitality Insurance",
        regions=["Southeast", "South Carolina", "SC", "Georgia", "GA", "Florida", "FL"],
        naics_specialties=["722410", "722511", "722513"],  # Bars, restaurants
        business_type_specialties=["bar", "tavern", "restaurant", "nightclub"],
        risk_appetite="moderate",
        average_turnaround_days=3,
        acceptance_rate=0.78,
        min_premium=5000,
        max_premium=500000,
        notes="Specializes in hospitality and entertainment venues in the Southeast",
    )


@pytest.fixture
def sample_construction_underwriter():
    """
    An underwriter who specializes in construction - poor match for bars.
    Used to test risk aversion penalty scoring.
    """
    return Underwriter(
        id="UW002",
        name="Bob Builder",
        company="Hardhat Insurance Group",
        regions=["Northeast", "New York", "NY", "New Jersey", "NJ"],
        naics_specialties=["236220", "236115", "238210"],  # Construction
        business_type_specialties=["construction", "contractor", "builder"],
        risk_appetite="high",
        average_turnaround_days=5,
        acceptance_rate=0.65,
        min_premium=10000,
        max_premium=1000000,
        notes="Specializes in commercial construction projects",
    )


@pytest.fixture
def sample_fast_underwriter():
    """
    A fast underwriter with quick turnaround but lower acceptance rate.
    """
    return Underwriter(
        id="UW003",
        name="Quick Quote Quinn",
        company="Rapid Response Insurance",
        regions=["Nationwide", "All States"],
        naics_specialties=["722410", "722511"],
        business_type_specialties=["bar", "restaurant"],
        risk_appetite="moderate",
        average_turnaround_days=1,
        acceptance_rate=0.60,
        min_premium=5000,
        max_premium=250000,
        notes="Known for fast quotes but selective acceptance",
    )


@pytest.fixture
def sample_high_acceptance_underwriter():
    """
    An underwriter with high acceptance rate but slower turnaround.
    """
    return Underwriter(
        id="UW004",
        name="Accepting Alice",
        company="Broad Coverage Insurance",
        regions=["Southeast", "South Carolina", "SC"],
        naics_specialties=["722410", "722511", "722513"],
        business_type_specialties=["bar", "restaurant", "cafe"],
        risk_appetite="low",
        average_turnaround_days=7,
        acceptance_rate=0.92,
        min_premium=3000,
        max_premium=300000,
        notes="High acceptance rate, thorough underwriting process",
    )


@pytest.fixture
def sample_extraction():
    """Sample DiscoveryCallExtraction for The Rusty Anchor"""
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
            hazards=["live entertainment", "alcohol service", "piano player"],
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


@pytest.fixture
def sample_transcript():
    """Load the actual transcript for integration tests"""
    try:
        with open("transcript.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        # Return a minimal transcript if file doesn't exist
        return """
        Broker: What's the business name?
        Client: It's called "The Rusty Anchor" at 450 Maple Avenue, Charleston, South Carolina 29401.
        Broker: What type of business is it?
        Client: It's a bar - we focus on high-end cocktails. We also have a piano player on weekends.
        Broker: Are you leasing or do you own the space?
        Client: Leasing.
        Broker: What are your projected annual revenues?
        Client: About $850,000. Around 70% from alcohol, 30% from food.
        Broker: Any current insurance?
        Client: Just Geico for my personal car. We need a specialized business policy ASAP.
        Broker: When can I call you?
        Client: Not tomorrow morning - my daughter has a dentist appointment. Tuesday afternoon works.
        """


# =============================================================================
# UNIT TESTS: underwriter_db.py
# =============================================================================

class TestUnderwriterDatabase:
    """Tests for the underwriter database module"""

    def test_get_all_underwriters_returns_10(self):
        """Verify the database contains exactly 10 underwriters"""
        underwriters = get_all_underwriters()
        assert len(underwriters) == 10, f"Expected 10 underwriters, got {len(underwriters)}"

    def test_get_all_underwriters_returns_list(self):
        """Verify get_all_underwriters returns a list of Underwriter objects"""
        underwriters = get_all_underwriters()
        assert isinstance(underwriters, list)
        for uw in underwriters:
            assert isinstance(uw, Underwriter)

    def test_get_underwriters_by_region(self):
        """Verify filtering by region works correctly"""
        # Test Southeast region
        southeast_uws = get_underwriters_by_region("Southeast")
        assert len(southeast_uws) > 0, "Should have at least one Southeast underwriter"
        for uw in southeast_uws:
            assert any(
                "southeast" in r.lower() or "sc" in r.lower() or "south carolina" in r.lower()
                for r in uw.regions
            ), f"Underwriter {uw.name} should cover Southeast"

    def test_get_underwriters_by_region_case_insensitive(self):
        """Region filtering should be case-insensitive"""
        uws_lower = get_underwriters_by_region("southeast")
        uws_upper = get_underwriters_by_region("SOUTHEAST")
        uws_mixed = get_underwriters_by_region("SouthEast")

        assert len(uws_lower) == len(uws_upper) == len(uws_mixed)

    def test_get_underwriters_by_naics(self):
        """Verify filtering by NAICS code works correctly"""
        # NAICS 722410 = Drinking Places (Alcoholic Beverages) - bars/taverns
        bar_specialists = get_underwriters_by_naics("722410")
        assert len(bar_specialists) > 0, "Should have at least one bar specialist"
        for uw in bar_specialists:
            assert "722410" in uw.naics_specialties, f"Underwriter {uw.name} should specialize in NAICS 722410"

    def test_get_underwriters_by_naics_returns_empty_for_unknown(self):
        """Unknown NAICS code should return empty list"""
        unknown_naics_uws = get_underwriters_by_naics("999999")
        assert len(unknown_naics_uws) == 0

    def test_underwriter_schema_validation(self):
        """Verify all underwriters have required fields"""
        underwriters = get_all_underwriters()
        required_fields = [
            "id", "name", "company", "regions", "naics_specialties",
            "average_turnaround_days", "acceptance_rate"
        ]

        for uw in underwriters:
            for field in required_fields:
                assert hasattr(uw, field), f"Underwriter missing required field: {field}"
                assert getattr(uw, field) is not None, f"Underwriter {uw.id} has null {field}"

    def test_underwriter_acceptance_rate_valid_range(self):
        """Acceptance rate should be between 0 and 1"""
        underwriters = get_all_underwriters()
        for uw in underwriters:
            assert 0 <= uw.acceptance_rate <= 1, \
                f"Underwriter {uw.id} has invalid acceptance rate: {uw.acceptance_rate}"

    def test_underwriter_turnaround_positive(self):
        """Turnaround days should be positive"""
        underwriters = get_all_underwriters()
        for uw in underwriters:
            assert uw.average_turnaround_days > 0, \
                f"Underwriter {uw.id} has invalid turnaround: {uw.average_turnaround_days}"

    def test_underwriter_unique_ids(self):
        """All underwriters should have unique IDs"""
        underwriters = get_all_underwriters()
        ids = [uw.id for uw in underwriters]
        assert len(ids) == len(set(ids)), "Underwriter IDs are not unique"


# =============================================================================
# UNIT TESTS: routing_engine.py
# =============================================================================

class TestRiskProfileExtraction:
    """Tests for extracting risk profile from mapped form output"""

    def test_extract_risk_profile(self, sample_mapped_output):
        """Verify NAICS, region, hazards extracted correctly from mapped output"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        assert isinstance(profile, RiskProfile)
        assert profile.naics_code == "722410"
        assert profile.state == "South Carolina"
        assert "Charleston" in profile.city
        assert "live entertainment" in profile.hazards or "piano" in str(profile.hazards).lower()

    def test_extract_risk_profile_includes_alcohol(self, sample_mapped_output):
        """Verify alcohol percentage is captured in risk profile"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        assert profile.alcohol_percentage == 70.0
        assert profile.liquor_liability_required is True

    def test_extract_risk_profile_includes_revenue(self, sample_mapped_output):
        """Verify annual revenue is captured in risk profile"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        assert profile.annual_revenue == 850000.0

    def test_extract_risk_profile_identifies_region(self, sample_mapped_output):
        """Verify region is correctly identified from state"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        # South Carolina should be identified as Southeast region
        assert profile.region == "Southeast"


class TestRegionMatchScoring:
    """Tests for region match scoring logic"""

    def test_region_match_scoring(self, sample_mapped_output, sample_underwriter):
        """Southeast underwriter should score higher for SC address"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        score = engine._score_region_match(profile, sample_underwriter)

        # Southeast underwriter should get high score for SC business
        assert score > 0, "Region match should produce positive score"
        assert score >= 0.8, "Southeast underwriter should score at least 0.8 for SC"

    def test_region_mismatch_scoring(self, sample_mapped_output, sample_construction_underwriter):
        """Northeast underwriter should score lower for SC address"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        score = engine._score_region_match(profile, sample_construction_underwriter)

        # Northeast underwriter should get low score for SC business
        assert score < 0.5, "Region mismatch should produce low score"

    def test_nationwide_underwriter_gets_moderate_score(self, sample_mapped_output, sample_fast_underwriter):
        """Nationwide underwriter should get moderate score for any region"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        score = engine._score_region_match(profile, sample_fast_underwriter)

        # Nationwide should get moderate score
        assert 0.4 <= score <= 0.7, "Nationwide underwriter should get moderate score"


class TestNAICSSpecialtyScoring:
    """Tests for NAICS specialty scoring logic"""

    def test_naics_specialty_scoring(self, sample_mapped_output, sample_underwriter):
        """Bar specialist should score higher for NAICS 722410"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        score = engine._score_naics_specialty(profile, sample_underwriter)

        # Bar specialist should get high score for bar
        assert score >= 0.9, "Bar specialist should score >= 0.9 for NAICS 722410"

    def test_naics_mismatch_scoring(self, sample_mapped_output, sample_construction_underwriter):
        """Construction specialist should score lower for bar NAICS"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        score = engine._score_naics_specialty(profile, sample_construction_underwriter)

        # Construction specialist should get low score for bar
        assert score < 0.3, "Construction specialist should score < 0.3 for bar"


class TestRiskAversionScoring:
    """Tests for risk aversion penalty scoring"""

    def test_risk_aversion_penalty(self, sample_mapped_output, sample_construction_underwriter):
        """Construction specialist should score lower for bar (wrong specialty)"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        # Overall score should be penalized due to specialty mismatch
        recommendations = engine.get_recommendations(sample_mapped_output, [sample_construction_underwriter])

        if recommendations:
            rec = recommendations[0]
            # Construction underwriter should have low overall score for bar
            assert rec.total_score < 50, "Construction specialist should have low score for bar"

    def test_high_risk_appetite_handles_hazards(self, sample_mapped_output, sample_underwriter):
        """Moderate risk appetite underwriter should handle entertainment hazards well"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        # Bar specialist with moderate risk appetite should handle bar well
        score = engine._score_risk_appetite(profile, sample_underwriter)

        assert score >= 0.6, "Moderate risk appetite should handle bar hazards adequately"


class TestTurnaroundScoring:
    """Tests for turnaround time scoring"""

    def test_turnaround_scoring(self, sample_fast_underwriter, sample_high_acceptance_underwriter):
        """Faster underwriter should score higher on turnaround"""
        engine = RoutingEngine()

        fast_score = engine._score_turnaround(sample_fast_underwriter)
        slow_score = engine._score_turnaround(sample_high_acceptance_underwriter)

        assert fast_score > slow_score, "Faster underwriter should score higher on turnaround"

    def test_turnaround_scoring_values(self, sample_fast_underwriter, sample_underwriter):
        """Verify turnaround scoring produces expected values"""
        engine = RoutingEngine()

        # 1-day turnaround should score very high
        fast_score = engine._score_turnaround(sample_fast_underwriter)
        assert fast_score >= 0.9, "1-day turnaround should score >= 0.9"

        # 3-day turnaround should score moderately high
        moderate_score = engine._score_turnaround(sample_underwriter)
        assert 0.6 <= moderate_score <= 0.9, "3-day turnaround should score between 0.6 and 0.9"


class TestAcceptanceRateScoring:
    """Tests for acceptance rate scoring"""

    def test_acceptance_rate_scoring(self, sample_high_acceptance_underwriter, sample_fast_underwriter):
        """Higher acceptance rate should score higher"""
        engine = RoutingEngine()

        high_score = engine._score_acceptance_rate(sample_high_acceptance_underwriter)
        low_score = engine._score_acceptance_rate(sample_fast_underwriter)

        assert high_score > low_score, "Higher acceptance rate underwriter should score higher"

    def test_acceptance_rate_values(self, sample_high_acceptance_underwriter):
        """Verify acceptance rate scoring produces expected values"""
        engine = RoutingEngine()

        # 92% acceptance rate should score very high
        score = engine._score_acceptance_rate(sample_high_acceptance_underwriter)
        assert score >= 0.9, "92% acceptance rate should score >= 0.9"


class TestRecommendationSorting:
    """Tests for recommendation sorting and ranking"""

    def test_recommendations_sorted_by_score(self, sample_mapped_output):
        """Top recommendation should have highest score"""
        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        recommendations = engine.get_recommendations(sample_mapped_output, underwriters)

        assert len(recommendations) > 0, "Should have at least one recommendation"

        # Verify sorted by total_score descending
        for i in range(len(recommendations) - 1):
            assert recommendations[i].total_score >= recommendations[i + 1].total_score, \
                "Recommendations should be sorted by score descending"

    def test_top_recommendation_is_best_match(self, sample_mapped_output, sample_underwriter,
                                               sample_construction_underwriter):
        """Bar specialist should be ranked above construction specialist for bar"""
        engine = RoutingEngine()

        recommendations = engine.get_recommendations(
            sample_mapped_output,
            [sample_construction_underwriter, sample_underwriter]  # Construction first
        )

        # Bar specialist should still be ranked first
        assert recommendations[0].underwriter.id == sample_underwriter.id, \
            "Bar specialist should be top recommendation for bar"


class TestJustificationGeneration:
    """Tests for recommendation justification"""

    def test_justification_contains_key_info(self, sample_mapped_output, sample_underwriter):
        """Justification should mention region, turnaround, and acceptance rate"""
        engine = RoutingEngine()

        recommendations = engine.get_recommendations(sample_mapped_output, [sample_underwriter])
        assert len(recommendations) > 0

        justification = recommendations[0].justification.lower()

        # Should mention key factors
        assert any(word in justification for word in ["southeast", "region", "south carolina", "sc"]), \
            "Justification should mention region match"
        assert any(word in justification for word in ["turnaround", "day", "quick", "fast"]), \
            "Justification should mention turnaround time"
        assert any(word in justification for word in ["acceptance", "rate", "percent", "%"]), \
            "Justification should mention acceptance rate"

    def test_justification_mentions_specialty(self, sample_mapped_output, sample_underwriter):
        """Justification should mention specialty match"""
        engine = RoutingEngine()

        recommendations = engine.get_recommendations(sample_mapped_output, [sample_underwriter])
        justification = recommendations[0].justification.lower()

        # Should mention specialty match
        assert any(word in justification for word in ["bar", "tavern", "hospitality", "722410", "specialty"]), \
            "Justification should mention specialty match"


class TestRoutingResult:
    """Tests for the complete routing result"""

    def test_routing_result_structure(self, sample_mapped_output):
        """Verify routing result has correct structure"""
        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        result = engine.route(sample_mapped_output, underwriters)

        assert isinstance(result, RoutingResult)
        assert hasattr(result, "risk_profile")
        assert hasattr(result, "recommendations")
        assert hasattr(result, "top_recommendation")

    def test_routing_result_has_top_recommendation(self, sample_mapped_output):
        """Verify routing result includes top recommendation"""
        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        result = engine.route(sample_mapped_output, underwriters)

        assert result.top_recommendation is not None
        assert isinstance(result.top_recommendation, UnderwriterRecommendation)

    def test_routing_result_scores_are_valid(self, sample_mapped_output):
        """Verify all scores are in valid range (0-100)"""
        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        result = engine.route(sample_mapped_output, underwriters)

        for rec in result.recommendations:
            assert 0 <= rec.total_score <= 100, f"Total score {rec.total_score} out of range"
            assert 0 <= rec.region_score <= 1, f"Region score {rec.region_score} out of range"
            assert 0 <= rec.specialty_score <= 1, f"Specialty score {rec.specialty_score} out of range"
            assert 0 <= rec.turnaround_score <= 1, f"Turnaround score {rec.turnaround_score} out of range"
            assert 0 <= rec.acceptance_score <= 1, f"Acceptance score {rec.acceptance_score} out of range"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.integration
class TestFullPipelineIntegration:
    """Integration tests for the complete Phase 1-3 pipeline"""

    def test_full_pipeline_phase1_to_phase3(self, sample_transcript):
        """End-to-end: transcript -> extraction -> mapping -> routing"""
        # Phase 1: Extract
        extraction = extract_from_transcript(sample_transcript)
        assert extraction is not None
        assert extraction.business_entity.dba is not None

        # Phase 2: Map
        mapped_output = map_extraction_to_forms(extraction)
        assert mapped_output is not None
        assert mapped_output.accord_125.business.naics_code is not None

        # Phase 3: Route
        engine = RoutingEngine()
        underwriters = get_all_underwriters()
        result = engine.route(mapped_output, underwriters)

        # Verify complete pipeline
        assert result is not None
        assert len(result.recommendations) > 0
        assert result.top_recommendation is not None
        assert result.top_recommendation.justification is not None

    def test_bar_routes_to_bar_specialist(self, sample_mapped_output):
        """The Rusty Anchor should route to bar specialist"""
        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        result = engine.route(sample_mapped_output, underwriters)
        top_rec = result.top_recommendation

        # Top recommendation should be a bar/hospitality specialist
        assert any(
            "722410" in top_rec.underwriter.naics_specialties or
            "bar" in str(top_rec.underwriter.business_type_specialties).lower() or
            "hospitality" in str(top_rec.underwriter.notes).lower()
        ), f"Top recommendation should be bar specialist, got {top_rec.underwriter.name}"

    def test_southeast_routes_to_southeast_underwriter(self, sample_mapped_output):
        """Charleston, SC should prefer Southeast underwriter"""
        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        result = engine.route(sample_mapped_output, underwriters)
        top_rec = result.top_recommendation

        # Top recommendation should cover Southeast region
        regions_lower = [r.lower() for r in top_rec.underwriter.regions]
        assert any(
            "southeast" in r or "sc" in r or "south carolina" in r or "nationwide" in r
            for r in regions_lower
        ), f"Top recommendation should cover Southeast, got regions: {top_rec.underwriter.regions}"

    def test_high_alcohol_triggers_liquor_liability_consideration(self, sample_mapped_output):
        """Bar with 70% alcohol should be routed considering liquor liability"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        assert profile.liquor_liability_required is True
        assert profile.alcohol_percentage == 70.0

        # Routing should consider this in scoring
        underwriters = get_all_underwriters()
        result = engine.route(sample_mapped_output, underwriters)

        # Justification should mention alcohol/liquor
        justification_lower = result.top_recommendation.justification.lower()
        assert any(
            word in justification_lower
            for word in ["alcohol", "liquor", "bar", "tavern", "drinking"]
        ), "Justification should consider liquor liability"

    def test_live_entertainment_captured_in_profile(self, sample_mapped_output):
        """Live entertainment hazard should be captured in risk profile"""
        engine = RoutingEngine()
        profile = engine.extract_risk_profile(sample_mapped_output)

        hazards_lower = [h.lower() for h in profile.hazards]
        has_entertainment = any(
            "entertainment" in h or "piano" in h or "music" in h
            for h in hazards_lower
        )
        assert has_entertainment, f"Profile should capture entertainment hazard, got: {profile.hazards}"


@pytest.mark.integration
class TestEdgeCases:
    """Integration tests for edge cases"""

    def test_empty_underwriter_list_returns_empty_recommendations(self, sample_mapped_output):
        """Routing with no underwriters should return empty recommendations"""
        engine = RoutingEngine()
        result = engine.route(sample_mapped_output, [])

        assert len(result.recommendations) == 0
        assert result.top_recommendation is None

    def test_missing_naics_still_routes(self, sample_mapped_output):
        """Routing should work even with missing NAICS code"""
        # Remove NAICS code
        sample_mapped_output.accord_125.business.naics_code = None
        sample_mapped_output.accord_126.classification.class_code = None

        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        # Should not raise exception
        result = engine.route(sample_mapped_output, underwriters)

        assert result is not None
        assert len(result.recommendations) > 0

    def test_routing_handles_partial_address(self, sample_mapped_output):
        """Routing should work with partial address information"""
        # Remove city
        sample_mapped_output.accord_125.premises.city = None

        engine = RoutingEngine()
        underwriters = get_all_underwriters()

        # Should not raise exception
        result = engine.route(sample_mapped_output, underwriters)

        assert result is not None


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require full pipeline)"
    )
