"""
Underwriter Database Module - Phase 3 of Computational Broker Engine

This module provides Pydantic models for underwriter data and a mock database
of underwriters with helper functions for querying by region and NAICS code.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Region(str, Enum):
    """Geographic regions for underwriter coverage."""
    SOUTHEAST = "Southeast"
    NORTHEAST = "Northeast"
    MIDWEST = "Midwest"
    SOUTHWEST = "Southwest"
    PNW = "PNW"
    WEST = "West"


class Workload(str, Enum):
    """Current workload levels for underwriters."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Underwriter(BaseModel):
    """
    Pydantic model representing an insurance underwriter.

    Attributes:
        name: Full name of the underwriter.
        email: Professional email address.
        phone: Contact phone number.
        region: Geographic region of coverage.
        risk_appetite: List of risk types the underwriter prefers.
        risk_aversions: List of risk types the underwriter avoids.
        naics_specialties: List of NAICS codes the underwriter specializes in.
        avg_turnaround_days: Average days to process a submission.
        acceptance_rate: Historical acceptance rate (0.0 to 1.0).
        current_workload: Current workload level.
        notes: Optional additional notes about the underwriter.
    """
    name: str
    email: str
    phone: str
    region: Region
    risk_appetite: list[str] = Field(description="Risk types the underwriter LIKES")
    risk_aversions: list[str] = Field(description="Risk types the underwriter AVOIDS")
    naics_specialties: list[str] = Field(description="NAICS codes of specialization")
    avg_turnaround_days: float = Field(ge=0.5, le=30.0)
    acceptance_rate: float = Field(ge=0.0, le=1.0)
    current_workload: Workload
    notes: Optional[str] = None


# Mock database of 10 underwriters with realistic data
UNDERWRITER_DATABASE: list[Underwriter] = [
    Underwriter(
        name="Sarah Mitchell",
        email="sarah.mitchell@insureco.com",
        phone="(404) 555-1234",
        region=Region.SOUTHEAST,
        risk_appetite=["Bars", "Restaurants", "Nightclubs", "Taverns"],
        risk_aversions=["Heavy Manufacturing", "Mining"],
        naics_specialties=["722410", "722511", "722513"],  # Drinking places, Full-service restaurants
        avg_turnaround_days=2.5,
        acceptance_rate=0.82,
        current_workload=Workload.MEDIUM,
        notes="15 years experience in hospitality sector. Prefers detailed loss runs."
    ),
    Underwriter(
        name="Michael Chen",
        email="m.chen@pacificuw.com",
        phone="(206) 555-5678",
        region=Region.PNW,
        risk_appetite=["Technology", "Software", "Professional Services"],
        risk_aversions=["Bars", "Nightclubs", "Cannabis"],
        naics_specialties=["541511", "541512", "541519"],  # Computer systems design
        avg_turnaround_days=1.5,
        acceptance_rate=0.88,
        current_workload=Workload.LOW,
        notes="Fast turnaround for tech companies. Requires cyber liability details."
    ),
    Underwriter(
        name="Jennifer Rodriguez",
        email="jrodriguez@sunbeltins.com",
        phone="(305) 555-9012",
        region=Region.SOUTHEAST,
        risk_appetite=["Restaurants", "Hotels", "Retail"],
        risk_aversions=["Construction", "Roofing"],
        naics_specialties=["722511", "721110", "445110"],  # Restaurants, Hotels, Grocery
        avg_turnaround_days=3.0,
        acceptance_rate=0.79,
        current_workload=Workload.HIGH,
        notes="Bilingual (English/Spanish). Strong relationships with Florida markets."
    ),
    Underwriter(
        name="David Thompson",
        email="david.t@midwestmutual.com",
        phone="(312) 555-3456",
        region=Region.MIDWEST,
        risk_appetite=["Manufacturing", "Warehousing", "Distribution"],
        risk_aversions=["Bars", "Adult Entertainment"],
        naics_specialties=["332999", "493110", "484110"],  # Manufacturing, Warehousing, Trucking
        avg_turnaround_days=4.0,
        acceptance_rate=0.71,
        current_workload=Workload.MEDIUM,
        notes="Extensive experience with product liability. Prefers face-to-face meetings."
    ),
    Underwriter(
        name="Amanda Foster",
        email="afoster@eastcoastuw.com",
        phone="(212) 555-7890",
        region=Region.NORTHEAST,
        risk_appetite=["Retail", "Professional Services", "Medical Offices"],
        risk_aversions=["Heavy Construction", "Hazardous Materials"],
        naics_specialties=["448140", "541110", "621111"],  # Retail, Legal, Medical
        avg_turnaround_days=2.0,
        acceptance_rate=0.85,
        current_workload=Workload.LOW,
        notes="Quick responses. Specializes in small to mid-market accounts."
    ),
    Underwriter(
        name="Robert Garcia",
        email="rgarcia@desertuw.com",
        phone="(602) 555-2345",
        region=Region.SOUTHWEST,
        risk_appetite=["Bars", "Restaurants", "Entertainment Venues"],
        risk_aversions=["Mining", "Oil & Gas"],
        naics_specialties=["722410", "722511", "713940"],  # Drinking places, Restaurants, Fitness centers
        avg_turnaround_days=3.5,
        acceptance_rate=0.76,
        current_workload=Workload.MEDIUM,
        notes="Strong liquor liability experience. Familiar with Arizona/Nevada regulations."
    ),
    Underwriter(
        name="Lisa Park",
        email="lpark@goldengate.com",
        phone="(415) 555-6789",
        region=Region.WEST,
        risk_appetite=["Technology Startups", "SaaS", "Fintech"],
        risk_aversions=["Heavy Manufacturing", "Agriculture"],
        naics_specialties=["541511", "522320", "518210"],  # Tech, Financial services, Data processing
        avg_turnaround_days=1.0,
        acceptance_rate=0.92,
        current_workload=Workload.HIGH,
        notes="Fastest turnaround in the region. Premium pricing but high acceptance rate."
    ),
    Underwriter(
        name="James Wilson",
        email="jwilson@atlanticins.com",
        phone="(617) 555-0123",
        region=Region.NORTHEAST,
        risk_appetite=["Construction", "Contractors", "Real Estate"],
        risk_aversions=["Restaurants", "Bars"],
        naics_specialties=["236220", "238210", "531210"],  # Construction, Electrical, Real estate
        avg_turnaround_days=5.0,
        acceptance_rate=0.68,
        current_workload=Workload.LOW,
        notes="Conservative underwriter. Thorough review process but reliable approvals."
    ),
    Underwriter(
        name="Maria Santos",
        email="msantos@heartlanduw.com",
        phone="(816) 555-4567",
        region=Region.MIDWEST,
        risk_appetite=["Agriculture", "Food Processing", "Retail"],
        risk_aversions=["Nightclubs", "Cannabis"],
        naics_specialties=["111998", "311999", "445110"],  # Agriculture, Food manufacturing, Grocery
        avg_turnaround_days=4.5,
        acceptance_rate=0.73,
        current_workload=Workload.MEDIUM,
        notes="Deep expertise in agricultural risks. Familiar with crop insurance programs."
    ),
    Underwriter(
        name="Kevin O'Brien",
        email="kobrien@peachstateuw.com",
        phone="(770) 555-8901",
        region=Region.SOUTHEAST,
        risk_appetite=["Restaurants", "Bars", "Breweries", "Wineries"],
        risk_aversions=["Heavy Industry", "Chemical Processing"],
        naics_specialties=["722410", "722511", "312120", "312130"],  # Bars, Restaurants, Breweries
        avg_turnaround_days=2.0,
        acceptance_rate=0.87,
        current_workload=Workload.LOW,
        notes="Hospitality specialist. Great for craft beverage accounts. Very responsive."
    ),
]


def get_all_underwriters() -> list[Underwriter]:
    """
    Retrieve all underwriters from the database.

    Returns:
        list[Underwriter]: Complete list of all underwriters in the database.

    Example:
        >>> underwriters = get_all_underwriters()
        >>> len(underwriters)
        10
    """
    return UNDERWRITER_DATABASE.copy()


def get_underwriters_by_region(region: Region | str) -> list[Underwriter]:
    """
    Retrieve underwriters filtered by geographic region.

    Args:
        region: The region to filter by. Can be a Region enum or string value.

    Returns:
        list[Underwriter]: List of underwriters covering the specified region.

    Raises:
        ValueError: If the region string doesn't match any valid region.

    Example:
        >>> southeast_uw = get_underwriters_by_region(Region.SOUTHEAST)
        >>> len(southeast_uw) >= 2
        True
    """
    if isinstance(region, str):
        try:
            region = Region(region)
        except ValueError:
            valid_regions = [r.value for r in Region]
            raise ValueError(f"Invalid region '{region}'. Valid regions: {valid_regions}")

    return [uw for uw in UNDERWRITER_DATABASE if uw.region == region]


def get_underwriters_by_naics(naics_code: str) -> list[Underwriter]:
    """
    Retrieve underwriters who specialize in a given NAICS code.

    Args:
        naics_code: The NAICS code to search for (e.g., "722410" for drinking places).

    Returns:
        list[Underwriter]: List of underwriters specializing in the given NAICS code.

    Example:
        >>> bar_specialists = get_underwriters_by_naics("722410")
        >>> len(bar_specialists) >= 2
        True
    """
    return [uw for uw in UNDERWRITER_DATABASE if naics_code in uw.naics_specialties]


def get_underwriters_by_risk_appetite(risk_type: str) -> list[Underwriter]:
    """
    Retrieve underwriters who have appetite for a specific risk type.

    Args:
        risk_type: The type of risk to search for (e.g., "Bars", "Restaurants").

    Returns:
        list[Underwriter]: List of underwriters with appetite for the risk type.

    Example:
        >>> restaurant_uw = get_underwriters_by_risk_appetite("Restaurants")
        >>> len(restaurant_uw) >= 1
        True
    """
    risk_type_lower = risk_type.lower()
    return [
        uw for uw in UNDERWRITER_DATABASE
        if any(risk_type_lower in appetite.lower() for appetite in uw.risk_appetite)
    ]


def get_available_underwriters(max_workload: Workload = Workload.MEDIUM) -> list[Underwriter]:
    """
    Retrieve underwriters with workload at or below the specified level.

    Args:
        max_workload: Maximum acceptable workload level. Defaults to Medium.

    Returns:
        list[Underwriter]: List of underwriters with acceptable workload levels.

    Example:
        >>> available = get_available_underwriters(Workload.LOW)
        >>> all(uw.current_workload == Workload.LOW for uw in available)
        True
    """
    workload_order = {Workload.LOW: 1, Workload.MEDIUM: 2, Workload.HIGH: 3}
    max_level = workload_order[max_workload]

    return [
        uw for uw in UNDERWRITER_DATABASE
        if workload_order[uw.current_workload] <= max_level
    ]


if __name__ == "__main__":
    # Demo usage
    print("=== Underwriter Database Demo ===\n")

    print(f"Total underwriters: {len(get_all_underwriters())}\n")

    print("Southeast Region Underwriters:")
    for uw in get_underwriters_by_region(Region.SOUTHEAST):
        print(f"  - {uw.name} ({uw.email}) - Acceptance Rate: {uw.acceptance_rate:.0%}")

    print("\nBar/Restaurant Specialists (NAICS 722410):")
    for uw in get_underwriters_by_naics("722410"):
        print(f"  - {uw.name} - Turnaround: {uw.avg_turnaround_days} days")

    print("\nUnderwriters with 'Restaurants' appetite:")
    for uw in get_underwriters_by_risk_appetite("Restaurants"):
        print(f"  - {uw.name} ({uw.region.value})")

    print("\nAvailable Underwriters (Low workload):")
    for uw in get_available_underwriters(Workload.LOW):
        print(f"  - {uw.name} - Acceptance Rate: {uw.acceptance_rate:.0%}")
