"""
Phase 1: Contextual Extraction for the Computational Broker Engine
Extracts structured data from discovery call transcripts using OpenAI + Instructor
"""

import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import openai
import instructor

# Load environment variables from .env file
load_dotenv()


# --- Pydantic Schema Definitions ---

class Address(BaseModel):
    """Physical address of the business"""
    street: str | None = Field(None, description="Street address")
    city: str | None = Field(None, description="City name")
    state: str | None = Field(None, description="State name or abbreviation")
    zip_code: str | None = Field(None, description="ZIP/Postal code")


class BusinessEntity(BaseModel):
    """Core business identification"""
    legal_name: str | None = Field(None, description="Official legal name of the business")
    dba: str | None = Field(None, description="Doing Business As / trade name")
    address: Address = Field(default_factory=Address)
    occupancy_type: str | None = Field(None, description="Leasing or Owning the premises")


class IndustryClassification(BaseModel):
    """Industry codes derived from business description"""
    naics_code: str | None = Field(None, description="NAICS code inferred from business type")
    sic_code: str | None = Field(None, description="SIC code inferred from business type")
    business_description: str = Field(..., description="Brief description of the business operations")


class RevenueDetails(BaseModel):
    """Financial projections and revenue breakdown"""
    gross_annual_sales: float | None = Field(None, description="Projected annual gross sales in USD")
    alcohol_percentage: float | None = Field(None, description="Percentage of revenue from alcohol sales")
    food_percentage: float | None = Field(None, description="Percentage of revenue from food sales")


class RiskFactors(BaseModel):
    """Specific hazards that affect the risk profile"""
    hazards: list[str] = Field(default_factory=list, description="List of specific risk factors (e.g., live music, deep fryer, late hours)")
    operating_hours: str | None = Field(None, description="Business operating hours if mentioned")
    special_features: list[str] = Field(default_factory=list, description="Special features that may impact risk (e.g., high-end cocktails)")


class InsuranceHistory(BaseModel):
    """
    Context Differentiation: Separates historical insurance data from current requirements.
    PRD Requirement: The LLM distinguishes between historical data (past providers) and current requirements.
    """
    past_carrier: str | None = Field(None, description="Previous insurance carrier name")
    past_carrier_context: str | None = Field(None, description="What the past carrier was used for (personal vs business)")
    current_need: str | None = Field(None, description="What type of coverage the client currently needs")
    urgency: str | None = Field(None, description="Timeline or urgency for binding coverage")


class SocialContext(BaseModel):
    """
    The Harper Touch: Non-business constraints for human-centered service.
    PRD Requirement: The system isolates non-business constraints, such as client availability.
    """
    availability_notes: str | None = Field(None, description="When the client is available or unavailable")
    preferred_contact_time: str | None = Field(None, description="Best time to contact the client")
    personal_constraints: str | None = Field(None, description="Personal events affecting availability (e.g., family events)")
    contact_restrictions: str | None = Field(None, description="Any specific restrictions on when NOT to contact")


class DiscoveryCallExtraction(BaseModel):
    """
    Complete extraction schema for Phase 1: Contextual Extraction.
    Maps to PRD requirements for:
    - Business Details (Entity, Industry, Revenue)
    - Risk Logic (Risk Factors)
    - Harper Touch (Social Context)
    """
    business_entity: BusinessEntity = Field(default_factory=BusinessEntity)
    industry_classification: IndustryClassification
    revenue_details: RevenueDetails = Field(default_factory=RevenueDetails)
    risk_factors: RiskFactors = Field(default_factory=RiskFactors)
    insurance_history: InsuranceHistory = Field(default_factory=InsuranceHistory)
    social_context: SocialContext = Field(default_factory=SocialContext)


# --- Extraction Logic ---

def extract_from_transcript(transcript: str) -> DiscoveryCallExtraction:
    """
    Process a discovery call transcript and extract structured data.
    Uses OpenAI with Instructor for structured output validation.
    """
    client = instructor.from_openai(openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY")))

    system_prompt = """You are an expert insurance data extraction agent for the "Computational Broker" system.

Your task is to extract structured data from discovery call transcripts with these critical requirements:

1. BUSINESS DETAILS: Extract legal name, DBA, address, and occupancy type accurately.

2. INDUSTRY CLASSIFICATION: Infer appropriate NAICS/SIC codes based on the business description.
   - Bars/Taverns: NAICS 722410, SIC 5813

3. RISK FACTORS: Identify ALL hazards that affect the risk profile:
   - Live entertainment (bands, piano players, DJs)
   - Alcohol service and percentage
   - Food preparation (deep fryers, grills)
   - Operating hours (late night increases risk)

4. CONTEXT DIFFERENTIATION (CRITICAL):
   - past_carrier: Historical insurance providers they HAD
   - past_carrier_context: What the past policy was for (personal vs business)
   - current_need: What they CURRENTLY need (specialized policy, etc.)
   - These MUST be separate - never conflate past providers with current requirements.

5. SOCIAL CONTEXT (The Harper Touch):
   - Extract ALL non-business constraints
   - Client availability windows
   - Personal events (appointments, family events)
   - Contact restrictions (when NOT to call)

Be precise. Never hallucinate data not present in the transcript. Leave fields null if not mentioned."""

    extraction = client.chat.completions.create(
        model="gpt-4o",
        response_model=DiscoveryCallExtraction,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract structured data from this discovery call transcript:\n\n{transcript}"}
        ]
    )

    return extraction


def main():
    """Main entry point - reads transcript and outputs extracted JSON"""
    import sys
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "transcript.txt"

    with open(transcript_path, "r") as f:
        transcript = f.read()

    print("=" * 60)
    print("PHASE 1: CONTEXTUAL EXTRACTION")
    print("The Computational Broker Engine")
    print("=" * 60)
    print()

    extraction = extract_from_transcript(transcript)

    # Output as formatted JSON
    output = extraction.model_dump(mode="json")

    print("EXTRACTED DATA:")
    print("-" * 60)
    print(json.dumps(output, indent=2))
    print("-" * 60)

    # Verification summary
    print()
    print("VERIFICATION SUMMARY:")
    print("-" * 60)
    print(f"✓ Business Entity: {extraction.business_entity.dba}")
    print(f"✓ Address: {extraction.business_entity.address.street}, {extraction.business_entity.address.city}, {extraction.business_entity.address.state}")
    print(f"✓ Industry: {extraction.industry_classification.naics_code}")
    print(f"✓ Risk Factors: {extraction.risk_factors.hazards}")
    print(f"✓ Past Carrier: {extraction.insurance_history.past_carrier} ({extraction.insurance_history.past_carrier_context})")
    print(f"✓ Current Need: {extraction.insurance_history.current_need}")
    print(f"✓ Harper Touch: {extraction.social_context.availability_notes}")
    print("-" * 60)

    return output


if __name__ == "__main__":
    main()
