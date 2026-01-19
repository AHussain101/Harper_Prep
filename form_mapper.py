"""
Phase 2: Structured Form Mapping (The Architect)
Maps extracted data to Accord 125/126 form schemas without hallucination.

Key Principles:
- Write once, populate many: One address fills all relevant form sections
- No hallucination: Missing fields stay null and become Broker Tasks
- Strict schema adherence: Mirrors actual Accord form field structure
"""

from datetime import date
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional

from extract import DiscoveryCallExtraction


# =============================================================================
# ENUMS FOR FORM FIELDS
# =============================================================================

class BusinessType(str, Enum):
    CORPORATION = "Corporation"
    LLC = "LLC"
    PARTNERSHIP = "Partnership"
    SOLE_PROPRIETOR = "Sole Proprietor"
    OTHER = "Other"


class PremisesOccupancy(str, Enum):
    OWNER = "Owner"
    TENANT = "Tenant"


class LiquorLiabilityType(str, Enum):
    SELL = "Sell"
    SERVE = "Serve"
    MANUFACTURE = "Manufacture"


# =============================================================================
# ACCORD 125 - COMMERCIAL INSURANCE APPLICATION
# =============================================================================

class Accord125_ApplicantInfo(BaseModel):
    """Section 1: Applicant Information"""
    applicant_name: Optional[str] = Field(None, description="Legal name of applicant")
    dba: Optional[str] = Field(None, description="Doing Business As")
    mailing_address: Optional[str] = Field(None)
    mailing_city: Optional[str] = Field(None)
    mailing_state: Optional[str] = Field(None)
    mailing_zip: Optional[str] = Field(None)
    business_phone: Optional[str] = Field(None)
    website: Optional[str] = Field(None)
    entity_type: Optional[BusinessType] = Field(None)
    fein: Optional[str] = Field(None, description="Federal Employer ID Number")


class Accord125_ContactInfo(BaseModel):
    """Section 2: Contact Information"""
    contact_name: Optional[str] = Field(None)
    contact_phone: Optional[str] = Field(None)
    contact_email: Optional[str] = Field(None)
    # Harper Touch fields (non-standard but critical for broker workflow)
    preferred_contact_time: Optional[str] = Field(None)
    contact_restrictions: Optional[str] = Field(None)


class Accord125_PremisesInfo(BaseModel):
    """Section 3: Premises Information"""
    location_number: int = Field(1, description="Location identifier")
    street_address: Optional[str] = Field(None)
    city: Optional[str] = Field(None)
    state: Optional[str] = Field(None)
    zip_code: Optional[str] = Field(None)
    occupancy: Optional[PremisesOccupancy] = Field(None, description="Owner or Tenant")
    year_built: Optional[int] = Field(None)
    square_footage: Optional[int] = Field(None)
    num_stories: Optional[int] = Field(None)


class Accord125_BusinessInfo(BaseModel):
    """Section 4: Business/Operations Information"""
    nature_of_business: Optional[str] = Field(None)
    sic_code: Optional[str] = Field(None)
    naics_code: Optional[str] = Field(None)
    years_in_business: Optional[int] = Field(None)
    years_management_experience: Optional[int] = Field(None)
    num_employees_full_time: Optional[int] = Field(None)
    num_employees_part_time: Optional[int] = Field(None)


class Accord125_RevenueInfo(BaseModel):
    """Section 5: Revenue/Sales Information"""
    annual_gross_sales: Optional[float] = Field(None)
    annual_payroll: Optional[float] = Field(None)


class Accord125_PriorInsurance(BaseModel):
    """Section 6: Prior Insurance Information"""
    prior_carrier: Optional[str] = Field(None)
    prior_policy_number: Optional[str] = Field(None)
    prior_expiration_date: Optional[date] = Field(None)
    years_with_prior_carrier: Optional[int] = Field(None)
    # Context differentiation: was prior coverage for this business?
    prior_coverage_type: Optional[str] = Field(None, description="What was the prior coverage for (personal/business)")


class Accord125_Form(BaseModel):
    """
    ACCORD 125 - Commercial Insurance Application
    Complete form structure with all sections
    """
    form_id: str = "ACCORD 125"
    form_name: str = "Commercial Insurance Application"

    applicant: Accord125_ApplicantInfo = Field(default_factory=Accord125_ApplicantInfo)
    contact: Accord125_ContactInfo = Field(default_factory=Accord125_ContactInfo)
    premises: Accord125_PremisesInfo = Field(default_factory=Accord125_PremisesInfo)
    business: Accord125_BusinessInfo = Field(default_factory=Accord125_BusinessInfo)
    revenue: Accord125_RevenueInfo = Field(default_factory=Accord125_RevenueInfo)
    prior_insurance: Accord125_PriorInsurance = Field(default_factory=Accord125_PriorInsurance)


# =============================================================================
# ACCORD 126 - COMMERCIAL GENERAL LIABILITY SECTION
# =============================================================================

class Accord126_ClassificationInfo(BaseModel):
    """Section 1: Classification and Rating Information"""
    class_code: Optional[str] = Field(None, description="GL class code")
    classification_description: Optional[str] = Field(None)
    premises_operations: bool = Field(True, description="Premises/Operations coverage needed")
    products_completed_ops: bool = Field(False, description="Products/Completed Operations coverage")


class Accord126_LiquorLiability(BaseModel):
    """Section 2: Liquor Liability (Critical for bars/restaurants)"""
    liquor_liability_required: bool = Field(False)
    liquor_liability_type: Optional[LiquorLiabilityType] = Field(None)
    alcohol_sales_percentage: Optional[float] = Field(None, description="% of revenue from alcohol")
    food_sales_percentage: Optional[float] = Field(None, description="% of revenue from food")
    annual_liquor_receipts: Optional[float] = Field(None)
    byob_allowed: Optional[bool] = Field(None)


class Accord126_EntertainmentExposure(BaseModel):
    """Section 3: Entertainment/Special Hazards"""
    live_entertainment: bool = Field(False)
    entertainment_description: Optional[str] = Field(None)
    dance_floor: bool = Field(False)
    pool_tables: bool = Field(False)
    games_arcade: bool = Field(False)
    cover_charge: bool = Field(False)


class Accord126_OperationsHazards(BaseModel):
    """Section 4: Operations Hazards"""
    hazards: list[str] = Field(default_factory=list)
    cooking_operations: bool = Field(False)
    deep_fryer: bool = Field(False)
    open_flame_cooking: bool = Field(False)
    delivery_operations: bool = Field(False)
    catering_operations: bool = Field(False)


class Accord126_HoursOperations(BaseModel):
    """Section 5: Hours of Operation"""
    opening_time: Optional[str] = Field(None)
    closing_time: Optional[str] = Field(None)
    days_open: Optional[str] = Field(None, description="e.g., Mon-Sun, Mon-Sat")
    late_night_operations: bool = Field(False, description="Open past midnight")


class Accord126_Form(BaseModel):
    """
    ACCORD 126 - Commercial General Liability Section
    Complete form structure for GL coverage
    """
    form_id: str = "ACCORD 126"
    form_name: str = "Commercial General Liability Section"

    classification: Accord126_ClassificationInfo = Field(default_factory=Accord126_ClassificationInfo)
    liquor_liability: Accord126_LiquorLiability = Field(default_factory=Accord126_LiquorLiability)
    entertainment: Accord126_EntertainmentExposure = Field(default_factory=Accord126_EntertainmentExposure)
    hazards: Accord126_OperationsHazards = Field(default_factory=Accord126_OperationsHazards)
    hours: Accord126_HoursOperations = Field(default_factory=Accord126_HoursOperations)


# =============================================================================
# BROKER TASKS - Missing Required Fields
# =============================================================================

class BrokerTask(BaseModel):
    """A follow-up task for missing required information"""
    field_name: str
    form_section: str
    form_id: str
    priority: str = Field("medium", description="high/medium/low")
    suggested_question: Optional[str] = Field(None, description="Suggested question to ask client")


class BrokerTaskList(BaseModel):
    """Collection of follow-up tasks for the broker"""
    tasks: list[BrokerTask] = Field(default_factory=list)
    total_missing_fields: int = 0

    def add_task(self, field_name: str, form_section: str, form_id: str,
                 priority: str = "medium", suggested_question: str = None):
        self.tasks.append(BrokerTask(
            field_name=field_name,
            form_section=form_section,
            form_id=form_id,
            priority=priority,
            suggested_question=suggested_question
        ))
        self.total_missing_fields += 1


# =============================================================================
# COMPLETE MAPPED OUTPUT
# =============================================================================

class MappedFormOutput(BaseModel):
    """
    Complete output of Phase 2: Form Mapping
    Contains populated forms and broker follow-up tasks
    """
    accord_125: Accord125_Form = Field(default_factory=Accord125_Form)
    accord_126: Accord126_Form = Field(default_factory=Accord126_Form)
    broker_tasks: BrokerTaskList = Field(default_factory=BrokerTaskList)
    mapping_summary: dict = Field(default_factory=dict)


# =============================================================================
# FORM MAPPER - The Architect
# =============================================================================

# Required fields that should generate Broker Tasks if missing
REQUIRED_FIELDS_125 = {
    "applicant.applicant_name": ("high", "What is the legal business name?"),
    "applicant.dba": ("high", "What name does the business operate under?"),
    "premises.street_address": ("high", "What is the business location address?"),
    "premises.city": ("high", "What city is the business located in?"),
    "premises.state": ("high", "What state is the business located in?"),
    "premises.zip_code": ("high", "What is the ZIP code?"),
    "business.naics_code": ("medium", "What is the NAICS code for this business?"),
    "revenue.annual_gross_sales": ("high", "What are the projected annual gross sales?"),
}

REQUIRED_FIELDS_126 = {
    "liquor_liability.alcohol_sales_percentage": ("high", "What percentage of sales is from alcohol?"),
    "liquor_liability.food_sales_percentage": ("medium", "What percentage of sales is from food?"),
}


class FormMapper:
    """
    Maps Phase 1 extraction output to Accord 125/126 forms.

    Principles:
    - Write once, populate many: Shared fields are written once
    - No hallucination: Missing data stays null
    - Broker Tasks: Missing required fields are flagged for follow-up
    """

    def __init__(self, extraction: DiscoveryCallExtraction):
        self.extraction = extraction
        self.output = MappedFormOutput()
        self.fields_populated = 0
        self.fields_missing = 0

    def map_all(self) -> MappedFormOutput:
        """Execute complete mapping from extraction to forms"""
        self._map_accord_125()
        self._map_accord_126()
        self._generate_broker_tasks()
        self._generate_summary()
        return self.output

    def _map_accord_125(self):
        """Map extraction data to Accord 125 form"""
        ext = self.extraction
        form = self.output.accord_125

        # Section 1: Applicant Info
        form.applicant.applicant_name = ext.business_entity.legal_name
        form.applicant.dba = ext.business_entity.dba

        # Write once, populate many: Address goes to both mailing and premises
        if ext.business_entity.address:
            addr = ext.business_entity.address
            form.applicant.mailing_address = addr.street
            form.applicant.mailing_city = addr.city
            form.applicant.mailing_state = addr.state
            form.applicant.mailing_zip = addr.zip_code

        # Section 2: Contact Info (Harper Touch integration)
        if ext.social_context:
            form.contact.preferred_contact_time = ext.social_context.preferred_contact_time
            form.contact.contact_restrictions = ext.social_context.contact_restrictions

        # Section 3: Premises Info (populated from same address - write once, populate many)
        if ext.business_entity.address:
            addr = ext.business_entity.address
            form.premises.street_address = addr.street
            form.premises.city = addr.city
            form.premises.state = addr.state
            form.premises.zip_code = addr.zip_code

        # Map occupancy type
        if ext.business_entity.occupancy_type:
            occ = ext.business_entity.occupancy_type.lower()
            if "leas" in occ or "tenant" in occ or "rent" in occ:
                form.premises.occupancy = PremisesOccupancy.TENANT
            elif "own" in occ:
                form.premises.occupancy = PremisesOccupancy.OWNER

        # Section 4: Business Info
        if ext.industry_classification:
            form.business.nature_of_business = ext.industry_classification.business_description
            form.business.sic_code = ext.industry_classification.sic_code
            form.business.naics_code = ext.industry_classification.naics_code

        # Section 5: Revenue Info
        if ext.revenue_details:
            form.revenue.annual_gross_sales = ext.revenue_details.gross_annual_sales

        # Section 6: Prior Insurance (with context differentiation)
        if ext.insurance_history:
            form.prior_insurance.prior_carrier = ext.insurance_history.past_carrier
            form.prior_insurance.prior_coverage_type = ext.insurance_history.past_carrier_context

    def _map_accord_126(self):
        """Map extraction data to Accord 126 form (General Liability)"""
        ext = self.extraction
        form = self.output.accord_126

        # Section 1: Classification
        if ext.industry_classification:
            form.classification.classification_description = ext.industry_classification.business_description
            form.classification.class_code = ext.industry_classification.naics_code

        # Section 2: Liquor Liability (critical for bars)
        if ext.revenue_details:
            alc_pct = ext.revenue_details.alcohol_percentage
            if alc_pct and alc_pct > 0:
                form.liquor_liability.liquor_liability_required = True
                form.liquor_liability.liquor_liability_type = LiquorLiabilityType.SELL
                form.liquor_liability.alcohol_sales_percentage = alc_pct
                form.liquor_liability.food_sales_percentage = ext.revenue_details.food_percentage

                # Calculate annual liquor receipts
                if ext.revenue_details.gross_annual_sales:
                    form.liquor_liability.annual_liquor_receipts = (
                        ext.revenue_details.gross_annual_sales * (alc_pct / 100)
                    )

        # Section 3: Entertainment Exposure
        if ext.risk_factors:
            hazards_lower = [h.lower() for h in ext.risk_factors.hazards]

            # Check for live entertainment
            entertainment_keywords = ["piano", "music", "band", "dj", "entertainment", "live"]
            for keyword in entertainment_keywords:
                if any(keyword in h for h in hazards_lower):
                    form.entertainment.live_entertainment = True
                    # Find the specific entertainment description
                    for h in ext.risk_factors.hazards:
                        if any(kw in h.lower() for kw in entertainment_keywords):
                            form.entertainment.entertainment_description = h
                            break
                    break

            # Check for other entertainment hazards
            if any("dance" in h for h in hazards_lower):
                form.entertainment.dance_floor = True
            if any("pool" in h for h in hazards_lower):
                form.entertainment.pool_tables = True

        # Section 4: Operations Hazards
        if ext.risk_factors:
            form.hazards.hazards = ext.risk_factors.hazards.copy()
            hazards_lower = [h.lower() for h in ext.risk_factors.hazards]

            # Check specific hazards
            if any("fryer" in h or "fry" in h for h in hazards_lower):
                form.hazards.deep_fryer = True
                form.hazards.cooking_operations = True
            if any("grill" in h or "flame" in h for h in hazards_lower):
                form.hazards.open_flame_cooking = True
                form.hazards.cooking_operations = True
            if any("delivery" in h for h in hazards_lower):
                form.hazards.delivery_operations = True
            if any("cater" in h for h in hazards_lower):
                form.hazards.catering_operations = True

        # Section 5: Hours of Operation
        if ext.risk_factors and ext.risk_factors.operating_hours:
            form.hours.opening_time = ext.risk_factors.operating_hours
            # Check for late night
            hours = ext.risk_factors.operating_hours.lower()
            if any(late in hours for late in ["1 am", "2 am", "3 am", "midnight", "1am", "2am"]):
                form.hours.late_night_operations = True

    def _generate_broker_tasks(self):
        """Generate follow-up tasks for missing required fields"""
        form_125 = self.output.accord_125
        form_126 = self.output.accord_126
        tasks = self.output.broker_tasks

        # Check Accord 125 required fields
        field_checks_125 = [
            ("applicant.applicant_name", form_125.applicant.applicant_name, "Applicant Info"),
            ("applicant.dba", form_125.applicant.dba, "Applicant Info"),
            ("premises.street_address", form_125.premises.street_address, "Premises Info"),
            ("premises.city", form_125.premises.city, "Premises Info"),
            ("premises.state", form_125.premises.state, "Premises Info"),
            ("premises.zip_code", form_125.premises.zip_code, "Premises Info"),
            ("business.naics_code", form_125.business.naics_code, "Business Info"),
            ("revenue.annual_gross_sales", form_125.revenue.annual_gross_sales, "Revenue Info"),
        ]

        for field_name, value, section in field_checks_125:
            if value is None:
                priority, question = REQUIRED_FIELDS_125.get(field_name, ("medium", None))
                tasks.add_task(field_name, section, "ACCORD 125", priority, question)

        # Check Accord 126 required fields (only if liquor liability applies)
        if self.output.accord_126.liquor_liability.liquor_liability_required:
            field_checks_126 = [
                ("liquor_liability.alcohol_sales_percentage",
                 form_126.liquor_liability.alcohol_sales_percentage, "Liquor Liability"),
            ]

            for field_name, value, section in field_checks_126:
                if value is None:
                    priority, question = REQUIRED_FIELDS_126.get(field_name, ("medium", None))
                    tasks.add_task(field_name, section, "ACCORD 126", priority, question)

    def _generate_summary(self):
        """Generate mapping summary statistics"""
        form_125 = self.output.accord_125
        form_126 = self.output.accord_126

        # Count populated vs missing in Accord 125
        populated_125 = 0
        total_125 = 0
        for section_name in ["applicant", "contact", "premises", "business", "revenue", "prior_insurance"]:
            section = getattr(form_125, section_name)
            for field_name, value in section.model_dump().items():
                if not field_name.startswith("_"):
                    total_125 += 1
                    if value is not None:
                        populated_125 += 1

        # Count populated in Accord 126
        populated_126 = 0
        total_126 = 0
        for section_name in ["classification", "liquor_liability", "entertainment", "hazards", "hours"]:
            section = getattr(form_126, section_name)
            for field_name, value in section.model_dump().items():
                if not field_name.startswith("_"):
                    total_126 += 1
                    if value is not None and value != [] and value != False:
                        populated_126 += 1

        self.output.mapping_summary = {
            "accord_125": {
                "populated_fields": populated_125,
                "total_fields": total_125,
                "completion_percentage": round((populated_125 / total_125) * 100, 1) if total_125 > 0 else 0
            },
            "accord_126": {
                "populated_fields": populated_126,
                "total_fields": total_126,
                "completion_percentage": round((populated_126 / total_126) * 100, 1) if total_126 > 0 else 0
            },
            "broker_tasks_count": self.output.broker_tasks.total_missing_fields,
            "write_once_populate_many": [
                "Address → Mailing Address + Premises Address",
                "NAICS Code → Business Info + GL Classification"
            ]
        }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def map_extraction_to_forms(extraction: DiscoveryCallExtraction) -> MappedFormOutput:
    """
    Main entry point: Map Phase 1 extraction to Accord forms.

    Args:
        extraction: Output from Phase 1 contextual extraction

    Returns:
        MappedFormOutput with populated Accord 125, 126, and broker tasks
    """
    mapper = FormMapper(extraction)
    return mapper.map_all()


def main():
    """Demo: Run full pipeline from transcript to mapped forms"""
    import json
    from extract import extract_from_transcript

    # Load transcript
    with open("transcript.txt", "r") as f:
        transcript = f.read()

    print("=" * 70)
    print("PHASE 2: STRUCTURED FORM MAPPING")
    print("The Computational Broker Engine - The Architect")
    print("=" * 70)
    print()

    # Phase 1: Extract
    print("Step 1: Running Phase 1 extraction...")
    extraction = extract_from_transcript(transcript)
    print("✓ Extraction complete")
    print()

    # Phase 2: Map
    print("Step 2: Mapping to Accord forms...")
    mapped_output = map_extraction_to_forms(extraction)
    print("✓ Mapping complete")
    print()

    # Output results
    print("=" * 70)
    print("ACCORD 125 - Commercial Insurance Application")
    print("=" * 70)
    print(json.dumps(mapped_output.accord_125.model_dump(), indent=2, default=str))
    print()

    print("=" * 70)
    print("ACCORD 126 - Commercial General Liability Section")
    print("=" * 70)
    print(json.dumps(mapped_output.accord_126.model_dump(), indent=2, default=str))
    print()

    print("=" * 70)
    print("BROKER TASKS - Follow-up Required")
    print("=" * 70)
    if mapped_output.broker_tasks.tasks:
        for task in mapped_output.broker_tasks.tasks:
            print(f"  [{task.priority.upper()}] {task.form_id} > {task.form_section} > {task.field_name}")
            if task.suggested_question:
                print(f"         → Ask: \"{task.suggested_question}\"")
    else:
        print("  No missing required fields!")
    print()

    print("=" * 70)
    print("MAPPING SUMMARY")
    print("=" * 70)
    summary = mapped_output.mapping_summary
    print(f"  Accord 125: {summary['accord_125']['populated_fields']}/{summary['accord_125']['total_fields']} fields ({summary['accord_125']['completion_percentage']}%)")
    print(f"  Accord 126: {summary['accord_126']['populated_fields']}/{summary['accord_126']['total_fields']} fields ({summary['accord_126']['completion_percentage']}%)")
    print(f"  Broker Tasks: {summary['broker_tasks_count']} follow-ups needed")
    print()
    print("  Write-Once-Populate-Many:")
    for item in summary["write_once_populate_many"]:
        print(f"    • {item}")
    print("=" * 70)

    return mapped_output


if __name__ == "__main__":
    main()
