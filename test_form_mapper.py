"""
Test suite for Phase 2: Structured Form Mapping
Tests schema validation, mapping logic, and broker task generation
"""

import pytest
import json
import os

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

from form_mapper import (
    Accord125_Form,
    Accord126_Form,
    PremisesOccupancy,
    LiquorLiabilityType,
    BrokerTask,
    BrokerTaskList,
    MappedFormOutput,
    FormMapper,
    map_extraction_to_forms,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_extraction():
    """Complete extraction matching transcript.txt"""
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
            hazards=["piano player", "high-end cocktails"],
            operating_hours=None,
            special_features=[]
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
def minimal_extraction():
    """Minimal extraction with many missing fields"""
    return DiscoveryCallExtraction(
        business_entity=BusinessEntity(
            dba="Test Bar"
        ),
        industry_classification=IndustryClassification(
            business_description="A bar"
        ),
        revenue_details=RevenueDetails(),
        risk_factors=RiskFactors(),
        insurance_history=InsuranceHistory(),
        social_context=SocialContext()
    )


@pytest.fixture
def sample_transcript():
    """Load the actual transcript.txt"""
    with open("transcript.txt", "r") as f:
        return f.read()


# =============================================================================
# UNIT TESTS: ACCORD 125 SCHEMA
# =============================================================================

class TestAccord125Schema:
    """Tests for Accord 125 form structure"""

    def test_empty_form_creation(self):
        """Empty form should have all sections with null fields"""
        form = Accord125_Form()
        assert form.form_id == "ACCORD 125"
        assert form.applicant.applicant_name is None
        assert form.premises.street_address is None

    def test_premises_occupancy_enum(self):
        """Occupancy should use proper enum values"""
        form = Accord125_Form()
        form.premises.occupancy = PremisesOccupancy.TENANT
        assert form.premises.occupancy == PremisesOccupancy.TENANT
        assert form.premises.occupancy.value == "Tenant"

    def test_form_serialization(self):
        """Form should serialize to JSON correctly"""
        form = Accord125_Form()
        form.applicant.dba = "Test Business"
        form.premises.city = "Charleston"

        json_str = form.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["applicant"]["dba"] == "Test Business"
        assert parsed["premises"]["city"] == "Charleston"


# =============================================================================
# UNIT TESTS: ACCORD 126 SCHEMA
# =============================================================================

class TestAccord126Schema:
    """Tests for Accord 126 form structure"""

    def test_liquor_liability_defaults(self):
        """Liquor liability should default to not required"""
        form = Accord126_Form()
        assert form.liquor_liability.liquor_liability_required is False
        assert form.liquor_liability.liquor_liability_type is None

    def test_entertainment_exposure_defaults(self):
        """Entertainment fields should default to False"""
        form = Accord126_Form()
        assert form.entertainment.live_entertainment is False
        assert form.entertainment.dance_floor is False

    def test_liquor_liability_type_enum(self):
        """Liquor liability type should use proper enum"""
        form = Accord126_Form()
        form.liquor_liability.liquor_liability_type = LiquorLiabilityType.SELL
        assert form.liquor_liability.liquor_liability_type.value == "Sell"


# =============================================================================
# UNIT TESTS: BROKER TASKS
# =============================================================================

class TestBrokerTasks:
    """Tests for Broker Task generation"""

    def test_add_broker_task(self):
        """Should be able to add tasks with all fields"""
        task_list = BrokerTaskList()
        task_list.add_task(
            field_name="applicant.dba",
            form_section="Applicant Info",
            form_id="ACCORD 125",
            priority="high",
            suggested_question="What is the business name?"
        )

        assert len(task_list.tasks) == 1
        assert task_list.total_missing_fields == 1
        assert task_list.tasks[0].field_name == "applicant.dba"
        assert task_list.tasks[0].priority == "high"

    def test_multiple_tasks(self):
        """Should track multiple tasks correctly"""
        task_list = BrokerTaskList()
        task_list.add_task("field1", "Section1", "ACCORD 125")
        task_list.add_task("field2", "Section2", "ACCORD 126")

        assert len(task_list.tasks) == 2
        assert task_list.total_missing_fields == 2


# =============================================================================
# UNIT TESTS: FORM MAPPER
# =============================================================================

class TestFormMapperWriteOncePopulateMany:
    """Tests for 'write once, populate many' logic"""

    def test_address_populates_both_sections(self, sample_extraction):
        """Address should populate both mailing and premises sections"""
        output = map_extraction_to_forms(sample_extraction)

        # Mailing address (Accord 125 Applicant section)
        assert output.accord_125.applicant.mailing_address == "450 Maple Avenue"
        assert output.accord_125.applicant.mailing_city == "Charleston"
        assert output.accord_125.applicant.mailing_state == "South Carolina"
        assert output.accord_125.applicant.mailing_zip == "29401"

        # Premises address (Accord 125 Premises section)
        assert output.accord_125.premises.street_address == "450 Maple Avenue"
        assert output.accord_125.premises.city == "Charleston"
        assert output.accord_125.premises.state == "South Carolina"
        assert output.accord_125.premises.zip_code == "29401"

    def test_naics_populates_multiple_forms(self, sample_extraction):
        """NAICS code should appear in both business info and GL classification"""
        output = map_extraction_to_forms(sample_extraction)

        assert output.accord_125.business.naics_code == "722410"
        assert output.accord_126.classification.class_code == "722410"


class TestFormMapperNoHallucination:
    """Tests for no-hallucination constraint"""

    def test_missing_fields_stay_null(self, minimal_extraction):
        """Fields not in extraction should remain null"""
        output = map_extraction_to_forms(minimal_extraction)

        # These were never in the extraction
        assert output.accord_125.applicant.applicant_name is None
        assert output.accord_125.premises.street_address is None
        assert output.accord_125.revenue.annual_gross_sales is None

    def test_missing_legal_name_stays_null(self, sample_extraction):
        """Legal name was not in transcript, must stay null"""
        output = map_extraction_to_forms(sample_extraction)
        assert output.accord_125.applicant.applicant_name is None


class TestFormMapperOccupancy:
    """Tests for occupancy type mapping"""

    def test_leasing_maps_to_tenant(self, sample_extraction):
        """'Leasing' should map to TENANT"""
        output = map_extraction_to_forms(sample_extraction)
        assert output.accord_125.premises.occupancy == PremisesOccupancy.TENANT

    def test_owning_maps_to_owner(self):
        """'Owning' should map to OWNER"""
        extraction = DiscoveryCallExtraction(
            business_entity=BusinessEntity(
                dba="Test",
                occupancy_type="Owning"
            ),
            industry_classification=IndustryClassification(
                business_description="Test business"
            )
        )
        output = map_extraction_to_forms(extraction)
        assert output.accord_125.premises.occupancy == PremisesOccupancy.OWNER


class TestFormMapperLiquorLiability:
    """Tests for liquor liability mapping"""

    def test_high_alcohol_triggers_liquor_liability(self, sample_extraction):
        """70% alcohol sales should trigger liquor liability"""
        output = map_extraction_to_forms(sample_extraction)

        assert output.accord_126.liquor_liability.liquor_liability_required is True
        assert output.accord_126.liquor_liability.liquor_liability_type == LiquorLiabilityType.SELL
        assert output.accord_126.liquor_liability.alcohol_sales_percentage == 70.0
        assert output.accord_126.liquor_liability.food_sales_percentage == 30.0

    def test_liquor_receipts_calculated(self, sample_extraction):
        """Annual liquor receipts should be calculated from gross sales"""
        output = map_extraction_to_forms(sample_extraction)

        # $850,000 * 70% = $595,000
        expected = 850000.0 * 0.70
        assert output.accord_126.liquor_liability.annual_liquor_receipts == expected

    def test_no_alcohol_no_liquor_liability(self, minimal_extraction):
        """No alcohol sales should not trigger liquor liability"""
        output = map_extraction_to_forms(minimal_extraction)
        assert output.accord_126.liquor_liability.liquor_liability_required is False


class TestFormMapperEntertainment:
    """Tests for entertainment/hazard mapping"""

    def test_piano_triggers_live_entertainment(self, sample_extraction):
        """Piano player should trigger live entertainment flag"""
        output = map_extraction_to_forms(sample_extraction)

        assert output.accord_126.entertainment.live_entertainment is True
        assert "piano" in output.accord_126.entertainment.entertainment_description.lower()

    def test_hazards_copied_to_form(self, sample_extraction):
        """Hazards list should be copied to Accord 126"""
        output = map_extraction_to_forms(sample_extraction)

        assert "piano player" in output.accord_126.hazards.hazards
        assert "high-end cocktails" in output.accord_126.hazards.hazards


class TestFormMapperHarperTouch:
    """Tests for Harper Touch (social context) mapping"""

    def test_contact_preferences_mapped(self, sample_extraction):
        """Social context should map to contact preferences"""
        output = map_extraction_to_forms(sample_extraction)

        assert output.accord_125.contact.preferred_contact_time == "Tuesday afternoon"
        assert output.accord_125.contact.contact_restrictions == "Don't call tomorrow morning"


class TestFormMapperBrokerTaskGeneration:
    """Tests for broker task generation"""

    def test_missing_required_fields_generate_tasks(self, minimal_extraction):
        """Missing required fields should generate broker tasks"""
        output = map_extraction_to_forms(minimal_extraction)

        assert output.broker_tasks.total_missing_fields > 0

        # Should have task for missing address
        field_names = [t.field_name for t in output.broker_tasks.tasks]
        assert "premises.street_address" in field_names

    def test_complete_extraction_fewer_tasks(self, sample_extraction):
        """Complete extraction should have fewer broker tasks"""
        output = map_extraction_to_forms(sample_extraction)

        # Only legal_name should be missing (it was null in extraction)
        task_fields = [t.field_name for t in output.broker_tasks.tasks]

        # Should have task for missing legal name
        assert "applicant.applicant_name" in task_fields

        # Should NOT have task for fields that were populated
        assert "premises.street_address" not in task_fields
        assert "applicant.dba" not in task_fields

    def test_broker_tasks_have_suggested_questions(self, minimal_extraction):
        """Broker tasks should include suggested follow-up questions"""
        output = map_extraction_to_forms(minimal_extraction)

        tasks_with_questions = [t for t in output.broker_tasks.tasks if t.suggested_question]
        assert len(tasks_with_questions) > 0


class TestFormMapperSummary:
    """Tests for mapping summary generation"""

    def test_summary_includes_completion_percentage(self, sample_extraction):
        """Summary should include completion percentages"""
        output = map_extraction_to_forms(sample_extraction)

        assert "accord_125" in output.mapping_summary
        assert "completion_percentage" in output.mapping_summary["accord_125"]
        assert output.mapping_summary["accord_125"]["completion_percentage"] > 0

    def test_summary_includes_broker_task_count(self, sample_extraction):
        """Summary should include broker task count"""
        output = map_extraction_to_forms(sample_extraction)
        assert "broker_tasks_count" in output.mapping_summary


# =============================================================================
# INTEGRATION TESTS: REAL API
# =============================================================================

@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping integration tests"
)
class TestIntegrationEndToEnd:
    """End-to-end integration tests: transcript → extraction → mapping"""

    def test_full_pipeline(self, sample_transcript):
        """Test complete pipeline from transcript to mapped forms"""
        # Phase 1: Extract
        extraction = extract_from_transcript(sample_transcript)

        # Phase 2: Map
        output = map_extraction_to_forms(extraction)

        # Verify Accord 125
        assert output.accord_125.applicant.dba == "The Rusty Anchor"
        assert output.accord_125.premises.street_address == "450 Maple Avenue"
        assert output.accord_125.premises.occupancy == PremisesOccupancy.TENANT
        assert output.accord_125.revenue.annual_gross_sales == 850000.0

        # Verify Accord 126
        assert output.accord_126.liquor_liability.liquor_liability_required is True
        assert output.accord_126.liquor_liability.alcohol_sales_percentage == 70.0
        assert output.accord_126.entertainment.live_entertainment is True

        # Verify Harper Touch preserved (at least one social context field mapped)
        harper_touch_present = (
            output.accord_125.contact.preferred_contact_time is not None or
            output.accord_125.contact.contact_restrictions is not None
        )
        assert harper_touch_present, "Harper Touch fields should be populated"

    def test_context_differentiation_preserved(self, sample_transcript):
        """Prior insurance context should be preserved through mapping"""
        extraction = extract_from_transcript(sample_transcript)
        output = map_extraction_to_forms(extraction)

        # Past carrier was for personal insurance
        assert output.accord_125.prior_insurance.prior_carrier == "Geico"
        assert "personal" in output.accord_125.prior_insurance.prior_coverage_type.lower()

    def test_no_hallucination_through_pipeline(self, sample_transcript):
        """Fields not in transcript should remain null through entire pipeline"""
        extraction = extract_from_transcript(sample_transcript)
        output = map_extraction_to_forms(extraction)

        # Legal name was never mentioned
        assert output.accord_125.applicant.applicant_name is None

        # FEIN was never mentioned
        assert output.accord_125.applicant.fein is None

        # Square footage was never mentioned
        assert output.accord_125.premises.square_footage is None

    def test_broker_tasks_generated_for_missing(self, sample_transcript):
        """Broker tasks should be generated for missing required fields"""
        extraction = extract_from_transcript(sample_transcript)
        output = map_extraction_to_forms(extraction)

        # Should have task for missing legal name
        task_fields = [t.field_name for t in output.broker_tasks.tasks]
        assert "applicant.applicant_name" in task_fields
