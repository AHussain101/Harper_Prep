"""
Phase 3: Intelligent Routing Engine (The Strategist)

This module implements the routing logic that matches extracted and mapped
insurance submissions to the most suitable underwriters based on multiple
weighted scoring criteria.
"""

from typing import Optional
from pydantic import BaseModel, Field

from form_mapper import MappedFormOutput
from underwriter_db import Underwriter, get_all_underwriters


# =============================================================================
# Pydantic Models
# =============================================================================

class RiskProfile(BaseModel):
    """
    Risk profile extracted from mapped form output.

    Contains the key attributes that influence underwriter matching:
    - Industry classification (NAICS)
    - Geographic region
    - Specific hazards and risk factors
    - Special coverages like liquor liability
    - Submission urgency
    """
    naics_code: Optional[str] = Field(
        default=None,
        description="NAICS code representing the business classification"
    )
    region: Optional[str] = Field(
        default=None,
        description="Geographic region of the business (e.g., Southeast, Northeast)"
    )
    hazards: list[str] = Field(
        default_factory=list,
        description="List of identified hazards (e.g., cooking equipment, alcohol service)"
    )
    liquor_liability: bool = Field(
        default=False,
        description="Whether liquor liability coverage is needed"
    )
    urgency: str = Field(
        default="standard",
        description="Urgency level: 'rush', 'standard', or 'flexible'"
    )
    business_type: Optional[str] = Field(
        default=None,
        description="Type of business (e.g., bar, restaurant, retail)"
    )
    annual_revenue: Optional[float] = Field(
        default=None,
        description="Annual revenue for sizing the risk"
    )


class UnderwriterScore(BaseModel):
    """
    Scoring result for a single underwriter.

    Contains the total score and a breakdown of how each
    scoring criterion contributed to the final score.
    """
    underwriter: Underwriter = Field(
        description="Reference to the scored underwriter"
    )
    total_score: float = Field(
        description="Total weighted score for this underwriter"
    )
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Score breakdown by criterion (e.g., {'region_match': 25, 'naics_specialty': 30})"
    )


class RoutingRecommendation(BaseModel):
    """
    Final routing recommendation with justification.

    Represents a recommended underwriter with explanation
    of why they were selected and alternative options.
    """
    recommended_underwriter: Underwriter = Field(
        description="The recommended underwriter for this submission"
    )
    score: float = Field(
        description="The underwriter's total score"
    )
    justification: str = Field(
        description="Human-readable explanation for the recommendation"
    )
    alternatives: list["RoutingRecommendation"] = Field(
        default_factory=list,
        description="Alternative underwriter recommendations ranked by score"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True


# =============================================================================
# Routing Engine
# =============================================================================

class RoutingEngine:
    """
    Intelligent Routing Engine for matching submissions to underwriters.

    The engine uses a weighted scoring system to evaluate each underwriter
    against the risk profile extracted from a submission. Scoring criteria
    include:

    - Region match (25 points): Exact geographic match
    - NAICS specialty (30 points): Underwriter specializes in the industry
    - Risk appetite (20 points): Underwriter preference for business type
    - Risk aversion penalty (-50 points): Underwriter avoids this type
    - Turnaround speed (15 points max): Faster processing preferred
    - Acceptance rate (10 points max): Higher acceptance rates preferred
    - Workload adjustment: Bonus/penalty based on current capacity

    Example:
        >>> engine = RoutingEngine()
        >>> recommendations = engine.get_recommendations(mapped_output, top_n=3)
        >>> for rec in recommendations:
        ...     print(rec.justification)
    """

    # Scoring weights
    REGION_MATCH_POINTS = 25
    NAICS_SPECIALTY_POINTS = 30
    RISK_APPETITE_POINTS = 20
    RISK_AVERSION_PENALTY = -50
    TURNAROUND_MAX_POINTS = 15
    ACCEPTANCE_RATE_MAX_POINTS = 10
    WORKLOAD_BONUS_MAX = 10
    WORKLOAD_PENALTY_MAX = -15

    # Turnaround benchmarks (in days)
    TURNAROUND_EXCELLENT = 1
    TURNAROUND_GOOD = 3
    TURNAROUND_AVERAGE = 5

    # Workload thresholds
    WORKLOAD_LOW = 0.5  # Less than 50% capacity
    WORKLOAD_HIGH = 0.85  # More than 85% capacity

    def __init__(self):
        """Initialize the routing engine."""
        self._underwriters: list[Underwriter] = []

    def extract_risk_profile(self, mapped_output: MappedFormOutput) -> RiskProfile:
        """
        Extract risk profile from mapped form output.

        Analyzes the mapped submission data to identify key risk
        characteristics that will be used for underwriter matching.

        Args:
            mapped_output: The mapped form output from Phase 2

        Returns:
            RiskProfile containing extracted risk characteristics
        """
        # Extract NAICS code from business classification
        naics_code = None
        if mapped_output.accord_125 and mapped_output.accord_125.business:
            naics_code = mapped_output.accord_125.business.naics_code

        # Extract region from premises location
        region = None
        if mapped_output.accord_125 and mapped_output.accord_125.premises:
            state = mapped_output.accord_125.premises.state
            if state:
                region = self._determine_region(state)

        # Extract hazards from Accord 126
        hazards = []
        if mapped_output.accord_126 and mapped_output.accord_126.hazards:
            hazards = mapped_output.accord_126.hazards.hazards.copy()

        # Check for liquor liability
        liquor_liability = False
        if mapped_output.accord_126 and mapped_output.accord_126.liquor_liability:
            liquor_liability = mapped_output.accord_126.liquor_liability.liquor_liability_required
            if liquor_liability and "alcohol_service" not in hazards:
                hazards.append("alcohol_service")

        # Check for entertainment hazards
        if mapped_output.accord_126 and mapped_output.accord_126.entertainment:
            if mapped_output.accord_126.entertainment.live_entertainment:
                if "live_entertainment" not in hazards:
                    hazards.append("live_entertainment")

        # Determine business type from NAICS or description
        business_type = self._classify_business_type(naics_code, mapped_output)

        # Extract urgency (default to standard)
        urgency = "standard"

        # Extract annual revenue
        annual_revenue = None
        if mapped_output.accord_125 and mapped_output.accord_125.revenue:
            annual_revenue = mapped_output.accord_125.revenue.annual_gross_sales

        return RiskProfile(
            naics_code=naics_code,
            region=region,
            hazards=hazards,
            liquor_liability=liquor_liability,
            urgency=urgency,
            business_type=business_type,
            annual_revenue=annual_revenue
        )

    def _determine_region(self, state: Optional[str]) -> Optional[str]:
        """
        Determine geographic region from state code or full state name.

        Args:
            state: Two-letter state code or full state name

        Returns:
            Region name (e.g., 'Southeast', 'Northeast')
        """
        if not state:
            return None

        state_upper = state.upper().strip()

        # Map full state names to abbreviations
        state_name_to_abbrev = {
            'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
            'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
            'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
            'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
            'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
            'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
            'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
            'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
            'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
            'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
            'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
            'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
            'WISCONSIN': 'WI', 'WYOMING': 'WY'
        }

        # Convert full name to abbreviation if needed
        if state_upper in state_name_to_abbrev:
            state_upper = state_name_to_abbrev[state_upper]

        region_mapping = {
            'Northeast': ['ME', 'NH', 'VT', 'MA', 'RI', 'CT', 'NY', 'NJ', 'PA'],
            'Southeast': ['DE', 'MD', 'VA', 'WV', 'NC', 'SC', 'GA', 'FL', 'KY', 'TN', 'AL', 'MS', 'AR', 'LA'],
            'Midwest': ['OH', 'MI', 'IN', 'IL', 'WI', 'MN', 'IA', 'MO', 'ND', 'SD', 'NE', 'KS'],
            'Southwest': ['TX', 'OK', 'NM', 'AZ'],
            'West': ['CO', 'WY', 'MT', 'ID', 'UT', 'NV', 'CA', 'OR', 'WA', 'AK', 'HI']
        }

        for region, states in region_mapping.items():
            if state_upper in states:
                return region

        return None

    def _classify_business_type(
        self,
        naics_code: Optional[str],
        mapped_output: MappedFormOutput
    ) -> Optional[str]:
        """
        Classify business type from NAICS code and other data.

        Args:
            naics_code: NAICS code if available
            mapped_output: Full mapped output for additional context

        Returns:
            Business type classification (e.g., 'bar', 'restaurant')
        """
        if not naics_code:
            return None

        # NAICS-based classification
        naics_classifications = {
            '722410': 'bar',  # Drinking Places (Alcoholic Beverages)
            '722511': 'restaurant',  # Full-Service Restaurants
            '722513': 'restaurant',  # Limited-Service Restaurants
            '722514': 'restaurant',  # Cafeterias
            '722515': 'restaurant',  # Snack and Nonalcoholic Beverage Bars
            '445110': 'retail',  # Supermarkets
            '445120': 'retail',  # Convenience Stores
            '448110': 'retail',  # Men's Clothing Stores
            '448120': 'retail',  # Women's Clothing Stores
            '721110': 'hotel',  # Hotels
            '721120': 'hotel',  # Casino Hotels
        }

        # Check exact match first
        if naics_code in naics_classifications:
            return naics_classifications[naics_code]

        # Check prefix match (first 4 digits)
        naics_prefix = naics_code[:4] if len(naics_code) >= 4 else naics_code
        prefix_classifications = {
            '7224': 'bar',
            '7225': 'restaurant',
            '4451': 'retail',
            '4481': 'retail',
            '7211': 'hotel',
        }

        if naics_prefix in prefix_classifications:
            return prefix_classifications[naics_prefix]

        return None

    def score_underwriter(
        self,
        underwriter: Underwriter,
        risk_profile: RiskProfile
    ) -> UnderwriterScore:
        """
        Score an underwriter against a risk profile.

        Evaluates the underwriter using weighted criteria and returns
        a detailed score breakdown.

        Args:
            underwriter: The underwriter to score
            risk_profile: The risk profile to match against

        Returns:
            UnderwriterScore with total score and breakdown
        """
        breakdown = {}
        total_score = 0.0

        # 1. Region Match (25 points)
        region_score = self._score_region_match(underwriter, risk_profile)
        breakdown['region_match'] = region_score
        total_score += region_score

        # 2. NAICS Specialty (30 points)
        naics_score = self._score_naics_specialty(underwriter, risk_profile)
        breakdown['naics_specialty'] = naics_score
        total_score += naics_score

        # 3. Risk Appetite (20 points) or Risk Aversion Penalty (-50 points)
        appetite_score = self._score_risk_appetite(underwriter, risk_profile)
        breakdown['risk_appetite'] = appetite_score
        total_score += appetite_score

        # 4. Turnaround Speed (15 points max)
        turnaround_score = self._score_turnaround(underwriter, risk_profile)
        breakdown['turnaround_speed'] = turnaround_score
        total_score += turnaround_score

        # 5. Acceptance Rate (10 points max)
        acceptance_score = self._score_acceptance_rate(underwriter)
        breakdown['acceptance_rate'] = acceptance_score
        total_score += acceptance_score

        # 6. Workload Adjustment (bonus or penalty)
        workload_score = self._score_workload(underwriter)
        breakdown['workload_adjustment'] = workload_score
        total_score += workload_score

        return UnderwriterScore(
            underwriter=underwriter,
            total_score=total_score,
            breakdown=breakdown
        )

    def _score_region_match(
        self,
        underwriter: Underwriter,
        risk_profile: RiskProfile
    ) -> float:
        """Score based on region match."""
        if not risk_profile.region:
            return 0.0

        # Check if underwriter serves this region
        if hasattr(underwriter, 'regions') and underwriter.regions:
            if risk_profile.region in underwriter.regions:
                return self.REGION_MATCH_POINTS
            # Partial credit for adjacent regions
            adjacent_regions = self._get_adjacent_regions(risk_profile.region)
            for region in underwriter.regions:
                if region in adjacent_regions:
                    return self.REGION_MATCH_POINTS * 0.5

        return 0.0

    def _get_adjacent_regions(self, region: str) -> list[str]:
        """Get regions adjacent to the given region."""
        adjacency = {
            'Northeast': ['Southeast', 'Midwest'],
            'Southeast': ['Northeast', 'Midwest', 'Southwest'],
            'Midwest': ['Northeast', 'Southeast', 'Southwest', 'West'],
            'Southwest': ['Southeast', 'Midwest', 'West'],
            'West': ['Midwest', 'Southwest']
        }
        return adjacency.get(region, [])

    def _score_naics_specialty(
        self,
        underwriter: Underwriter,
        risk_profile: RiskProfile
    ) -> float:
        """Score based on NAICS code specialty."""
        if not risk_profile.naics_code:
            return 0.0

        # Check if underwriter specializes in this NAICS
        if hasattr(underwriter, 'naics_specialties') and underwriter.naics_specialties:
            # Exact match
            if risk_profile.naics_code in underwriter.naics_specialties:
                return self.NAICS_SPECIALTY_POINTS

            # Prefix match (same industry group)
            naics_prefix = risk_profile.naics_code[:4]
            for specialty in underwriter.naics_specialties:
                if specialty.startswith(naics_prefix):
                    return self.NAICS_SPECIALTY_POINTS * 0.7

        return 0.0

    def _score_risk_appetite(
        self,
        underwriter: Underwriter,
        risk_profile: RiskProfile
    ) -> float:
        """
        Score based on risk appetite or apply aversion penalty.

        Returns positive points if underwriter likes this type,
        or negative penalty if they avoid it.
        """
        if not risk_profile.business_type:
            return 0.0

        # Check risk appetite (what they like)
        if hasattr(underwriter, 'risk_appetite') and underwriter.risk_appetite:
            if risk_profile.business_type in underwriter.risk_appetite:
                return self.RISK_APPETITE_POINTS

        # Check risk aversions (what they avoid)
        if hasattr(underwriter, 'risk_aversions') and underwriter.risk_aversions:
            if risk_profile.business_type in underwriter.risk_aversions:
                return self.RISK_AVERSION_PENALTY

            # Check for specific hazard aversions
            for hazard in risk_profile.hazards:
                if hazard in underwriter.risk_aversions:
                    return self.RISK_AVERSION_PENALTY

        return 0.0

    def _score_turnaround(
        self,
        underwriter: Underwriter,
        risk_profile: RiskProfile
    ) -> float:
        """Score based on average turnaround time."""
        if not hasattr(underwriter, 'avg_turnaround_days'):
            return 0.0

        turnaround = underwriter.avg_turnaround_days

        # Apply urgency multiplier
        urgency_multiplier = 1.0
        if risk_profile.urgency == 'rush':
            urgency_multiplier = 1.5  # Rush submissions weight turnaround more
        elif risk_profile.urgency == 'flexible':
            urgency_multiplier = 0.5  # Flexible submissions care less

        # Calculate score based on turnaround
        if turnaround <= self.TURNAROUND_EXCELLENT:
            base_score = self.TURNAROUND_MAX_POINTS
        elif turnaround <= self.TURNAROUND_GOOD:
            base_score = self.TURNAROUND_MAX_POINTS * 0.8
        elif turnaround <= self.TURNAROUND_AVERAGE:
            base_score = self.TURNAROUND_MAX_POINTS * 0.5
        else:
            base_score = self.TURNAROUND_MAX_POINTS * 0.2

        return min(base_score * urgency_multiplier, self.TURNAROUND_MAX_POINTS)

    def _score_acceptance_rate(self, underwriter: Underwriter) -> float:
        """Score based on historical acceptance rate."""
        if not hasattr(underwriter, 'acceptance_rate'):
            return 0.0

        # Scale acceptance rate to points (0-100% -> 0-10 points)
        return (underwriter.acceptance_rate / 100) * self.ACCEPTANCE_RATE_MAX_POINTS

    def _score_workload(self, underwriter: Underwriter) -> float:
        """Score adjustment based on current workload (Low/Medium/High enum)."""
        if not hasattr(underwriter, 'current_workload'):
            return 0.0

        workload = underwriter.current_workload

        # Convert workload enum to score adjustment
        # Low workload = bonus, High workload = penalty
        from underwriter_db import Workload
        if workload == Workload.LOW:
            return self.WORKLOAD_BONUS_MAX  # +10 bonus for available capacity
        elif workload == Workload.HIGH:
            return self.WORKLOAD_PENALTY_MAX  # -15 penalty for overloaded
        else:  # MEDIUM
            return 0.0  # No adjustment for normal workload

    def get_recommendations(
        self,
        mapped_output: MappedFormOutput,
        top_n: int = 3
    ) -> list[RoutingRecommendation]:
        """
        Get top N underwriter recommendations for a submission.

        Extracts the risk profile, scores all underwriters, and returns
        the top matches with justifications.

        Args:
            mapped_output: The mapped form output from Phase 2
            top_n: Number of recommendations to return (default: 3)

        Returns:
            List of RoutingRecommendation objects, ranked by score
        """
        # Extract risk profile
        risk_profile = self.extract_risk_profile(mapped_output)

        # Get all underwriters
        underwriters = get_all_underwriters()

        # Score each underwriter
        scores: list[UnderwriterScore] = []
        for underwriter in underwriters:
            score = self.score_underwriter(underwriter, risk_profile)
            scores.append(score)

        # Sort by total score (descending)
        scores.sort(key=lambda x: x.total_score, reverse=True)

        # Generate recommendations for top N
        recommendations: list[RoutingRecommendation] = []

        for i, score in enumerate(scores[:top_n]):
            justification = self._generate_justification(score, risk_profile)

            # For the top recommendation, include alternatives
            if i == 0:
                alternatives = [
                    RoutingRecommendation(
                        recommended_underwriter=alt_score.underwriter,
                        score=alt_score.total_score,
                        justification=self._generate_justification(alt_score, risk_profile),
                        alternatives=[]
                    )
                    for alt_score in scores[1:top_n]
                ]
            else:
                alternatives = []

            recommendations.append(RoutingRecommendation(
                recommended_underwriter=score.underwriter,
                score=score.total_score,
                justification=justification,
                alternatives=alternatives
            ))

        return recommendations

    def _generate_justification(
        self,
        score: UnderwriterScore,
        risk_profile: RiskProfile
    ) -> str:
        """
        Generate human-readable justification for a recommendation.

        Creates an explanation of why this underwriter was selected,
        highlighting key matching criteria.

        Args:
            score: The underwriter's score breakdown
            risk_profile: The risk profile being matched

        Returns:
            Human-readable justification string
        """
        underwriter = score.underwriter
        breakdown = score.breakdown

        # Start with the recommendation
        name = getattr(underwriter, 'name', 'Unknown')
        reasons = []

        # Highlight key positive factors
        if breakdown.get('naics_specialty', 0) > 0:
            business_type = risk_profile.business_type or "this industry"
            naics = risk_profile.naics_code or ""
            if naics:
                reasons.append(f"Specializes in {business_type}s (NAICS {naics})")
            else:
                reasons.append(f"Specializes in {business_type}s")

        if breakdown.get('region_match', 0) > 0:
            region = risk_profile.region or "the region"
            reasons.append(f"covers the {region} region")

        if breakdown.get('risk_appetite', 0) > 0:
            business_type = risk_profile.business_type or "this type of business"
            reasons.append(f"has appetite for {business_type}s")

        # Add performance metrics
        metrics = []
        if hasattr(underwriter, 'avg_turnaround_days'):
            days = underwriter.avg_turnaround_days
            metrics.append(f"{days}-day turnaround")

        if hasattr(underwriter, 'acceptance_rate'):
            rate = underwriter.acceptance_rate
            metrics.append(f"{rate}% acceptance rate")

        # Build the justification
        justification = f"Recommendation: {name}."

        if reasons:
            reasons_str = reasons[0].capitalize()
            if len(reasons) > 1:
                reasons_str += " and " + ", ".join(reasons[1:])
            justification += f" Reason: {reasons_str}."

        if metrics:
            justification += f" Averages {' with '.join(metrics)}."

        # Note any concerns
        if breakdown.get('workload_adjustment', 0) < -5:
            justification += " Note: Currently at high workload capacity."

        return justification


# =============================================================================
# Main Function
# =============================================================================

def main():
    """
    Main function demonstrating the complete routing pipeline.

    Loads a transcript, runs through all three phases:
    1. Extract structured data from transcript
    2. Map extraction to ACORD forms
    3. Route to recommended underwriters

    Prints the top 3 recommendations with justifications.
    """
    print("=" * 70)
    print("Phase 3: Intelligent Routing Engine")
    print("=" * 70)

    # Load transcript
    print("\n[1] Loading transcript...")
    try:
        with open("transcript.txt", "r") as f:
            transcript = f.read()
        print(f"    Loaded transcript ({len(transcript)} characters)")
    except FileNotFoundError:
        print("    ERROR: transcript.txt not found")
        print("    Please ensure transcript.txt exists in the current directory")
        return

    # Phase 1: Extract from transcript
    print("\n[2] Running Phase 1: Extraction...")
    try:
        from extract import extract_from_transcript
        extraction_result = extract_from_transcript(transcript)
        print("    Extraction complete")
    except ImportError:
        print("    ERROR: Could not import from extract module")
        print("    Please ensure extract.py exists with extract_from_transcript function")
        return
    except Exception as e:
        print(f"    ERROR during extraction: {e}")
        return

    # Phase 2: Map to forms
    print("\n[3] Running Phase 2: Form Mapping...")
    try:
        from form_mapper import map_extraction_to_forms
        mapped_output = map_extraction_to_forms(extraction_result)
        print("    Form mapping complete")
    except ImportError:
        print("    ERROR: Could not import from form_mapper module")
        print("    Please ensure form_mapper.py exists with map_extraction_to_forms function")
        return
    except Exception as e:
        print(f"    ERROR during form mapping: {e}")
        return

    # Phase 3: Route to underwriters
    print("\n[4] Running Phase 3: Routing...")
    engine = RoutingEngine()

    # Extract and display risk profile
    risk_profile = engine.extract_risk_profile(mapped_output)
    print("\n    Risk Profile:")
    print(f"      - NAICS Code: {risk_profile.naics_code}")
    print(f"      - Region: {risk_profile.region}")
    print(f"      - Business Type: {risk_profile.business_type}")
    print(f"      - Hazards: {', '.join(risk_profile.hazards) if risk_profile.hazards else 'None identified'}")
    print(f"      - Liquor Liability: {'Yes' if risk_profile.liquor_liability else 'No'}")
    print(f"      - Urgency: {risk_profile.urgency}")

    # Get recommendations
    recommendations = engine.get_recommendations(mapped_output, top_n=3)

    # Display recommendations
    print("\n" + "=" * 70)
    print("TOP 3 UNDERWRITER RECOMMENDATIONS")
    print("=" * 70)

    for i, rec in enumerate(recommendations, 1):
        underwriter = rec.recommended_underwriter
        name = getattr(underwriter, 'name', 'Unknown')

        print(f"\n#{i}: {name}")
        print(f"    Score: {rec.score:.1f} points")
        print(f"    {rec.justification}")

        # Show score breakdown
        if i == 1 and hasattr(recommendations[0], 'alternatives'):
            # For the top recommendation, we got the full score from the engine
            # Show breakdown if we can access it
            pass

    print("\n" + "=" * 70)
    print("Routing complete.")


if __name__ == "__main__":
    main()
