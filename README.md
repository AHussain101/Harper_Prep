# Computational Broker Engine

> An intelligent agent that processes insurance discovery call transcripts, extracts structured data, maps to industry-standard forms, and routes submissions to optimal underwriters.

**Built for Aarfans Brokerage** | [View Demo](demo.html)

---

## Overview

The Computational Broker Engine transforms the traditional insurance brokerage workflow from manual data entry into an intelligent, automated pipeline. Instead of brokers spending hours transcribing calls and filling forms, the system:

1. **Listens** to discovery calls and extracts structured data
2. **Maps** that data to ACORD 125/126 forms automatically
3. **Routes** submissions to the best-matched underwriter
4. **Schedules** follow-ups respecting client availability

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Phase 1   │    │   Phase 2   │    │   Phase 3   │    │   Phase 4   │
│  Listener   │ →  │  Architect  │ →  │ Strategist  │ →  │   Closer    │
│             │    │             │    │             │    │             │
│  Extract    │    │  Map to     │    │  Route to   │    │  Schedule   │
│  from calls │    │  ACORD forms│    │  underwriter│    │  & execute  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Quick Start

```bash
# 1. Clone and setup
cd Harper_Prep
python -m venv .venv
source .venv/bin/activate
pip install openai instructor pydantic python-dotenv pytest

# 2. Configure API key
echo "OPENAI_API_KEY=your-key-here" > .env

# 3. Run the full pipeline
python execution_engine.py

# 4. View the demo
open demo.html
```

---

## Architecture

### Phase 1: Contextual Extraction (The Listener)

**File:** `extract.py`

**Purpose:** Convert noisy conversation transcripts into clean, structured JSON.

**How it works:**
1. Takes raw transcript text as input
2. Sends to GPT-4o with a structured extraction prompt
3. Uses [Instructor](https://github.com/jxnl/instructor) library to enforce Pydantic schema validation
4. Returns validated `DiscoveryCallExtraction` object

**Key Features:**
- **Entity Extraction:** Business name, DBA, address, NAICS/SIC codes
- **Context Differentiation:** Separates historical data (past carriers) from current requirements
- **Aarfans Brokerage Touch:** Captures social availability and personal constraints

```python
# Example usage
from extract import extract_from_transcript

with open("transcript.txt") as f:
    transcript = f.read()

extraction = extract_from_transcript(transcript)
print(extraction.business_entity.dba)  # "The Rusty Anchor"
print(extraction.social_context.availability_notes)  # "Unavailable until 1:00 PM Tuesday"
```

**Output Schema:**
```
DiscoveryCallExtraction
├── business_entity
│   ├── legal_name: str | None
│   ├── dba: str | None
│   ├── address: Address
│   └── occupancy_type: str | None
├── industry_classification
│   ├── naics_code: str | None
│   ├── sic_code: str | None
│   └── business_description: str
├── revenue_details
│   ├── gross_annual_sales: float | None
│   ├── alcohol_percentage: float | None
│   └── food_percentage: float | None
├── risk_factors
│   ├── hazards: list[str]
│   └── operating_hours: str | None
├── insurance_history
│   ├── past_carrier: str | None          ← Historical
│   ├── past_carrier_context: str | None  ← "personal" vs "business"
│   └── current_need: str | None          ← Current requirement
└── social_context                        ← Aarfans Brokerage Touch
    ├── availability_notes: str | None
    ├── preferred_contact_time: str | None
    ├── personal_constraints: str | None
    └── contact_restrictions: str | None
```

---

### Phase 2: Structured Form Mapping (The Architect)

**File:** `form_mapper.py`

**Purpose:** Map extracted data to ACORD 125/126 form schemas without hallucination.

**How it works:**
1. Takes `DiscoveryCallExtraction` from Phase 1
2. Maps fields to corresponding ACORD form sections
3. Applies "write once, populate many" logic
4. Flags missing required fields as Broker Tasks

**Key Features:**
- **ACORD 125:** Commercial Insurance Application (applicant info, premises, revenue)
- **ACORD 126:** Commercial General Liability (liquor liability, entertainment, hazards)
- **No Hallucination:** Missing fields stay `null` and become follow-up tasks
- **Write Once, Populate Many:** Address extracted once fills both mailing and premises sections

```python
# Example usage
from extract import extract_from_transcript
from form_mapper import map_extraction_to_forms

extraction = extract_from_transcript(transcript)
mapped = map_extraction_to_forms(extraction)

print(mapped.accord_125.premises.city)  # "Charleston"
print(mapped.accord_126.liquor_liability.liquor_liability_required)  # True
print(mapped.broker_tasks.tasks[0].suggested_question)  # "What is the legal business name?"
```

**Mapping Logic:**
```
Extraction Field                    ACORD 125 Field              ACORD 126 Field
─────────────────────────────────────────────────────────────────────────────────
business_entity.address          →  applicant.mailing_*    +    (n/a)
                                    premises.*
business_entity.occupancy_type   →  premises.occupancy          (n/a)
industry_classification.naics    →  business.naics_code         classification.class_code
revenue_details.alcohol_pct      →  (n/a)                       liquor_liability.*
risk_factors.hazards             →  (n/a)                       hazards.hazards
```

---

### Phase 3: Intelligent Routing (The Strategist)

**File:** `routing_engine.py`, `underwriter_db.py`

**Purpose:** Match the risk profile to the optimal underwriter using weighted scoring.

**How it works:**
1. Extracts risk profile from mapped forms (NAICS, region, hazards, liquor liability)
2. Scores each underwriter in the database against the profile
3. Returns top 3 recommendations with justifications

**Scoring Criteria:**
| Criterion | Points | Description |
|-----------|--------|-------------|
| Region Match | 25 | Exact geographic match (Southeast UW for SC business) |
| NAICS Specialty | 30 | Underwriter specializes in the industry code |
| Risk Appetite | 20 | Underwriter prefers this business type |
| Risk Aversion | -50 | Penalty if underwriter avoids this type |
| Turnaround Speed | 15 max | Faster processing = more points |
| Acceptance Rate | 10 max | Higher acceptance = more points |
| Workload | ±10-15 | Bonus for low workload, penalty for high |

```python
# Example usage
from routing_engine import RoutingEngine
from underwriter_db import get_all_underwriters

engine = RoutingEngine()
underwriters = get_all_underwriters()
recommendations = engine.get_recommendations(mapped_output, top_n=3)

for rec in recommendations:
    print(f"{rec.recommended_underwriter.name}: {rec.score} pts")
    print(f"  {rec.justification}")
```

**Sample Output:**
```
#1: Kevin O'Brien - 52.1 pts
    Specializes in NAICS 722410 (bars) in Southeast. 2-day turnaround, 87% acceptance.

#2: Sarah Mitchell - 42.1 pts
    Hospitality specialist in Southeast. 2.5-day turnaround, 82% acceptance.

#3: Robert Garcia - 37.6 pts
    Bar specialist in Southwest. 3.5-day turnaround, 76% acceptance.
```

---

### Phase 4: Execution Engine (The Closer)

**File:** `execution_engine.py`

**Purpose:** Manage submission state and schedule actions based on social context.

**How it works:**
1. Tracks submission through states: Received → Extracted → Mapped → Routed → Scheduled
2. Parses social context to determine optimal contact time
3. Schedules actions respecting client constraints
4. Generates executive summary for broker review

**Temporal Logic (Aarfans Brokerage Touch):**
```
Client says                          System schedules
───────────────────────────────────────────────────────
"Don't call tomorrow morning"    →   Afternoon or next day
"Unavailable until Tuesday 1PM"  →   Tuesday 1:30 PM
"I'm at my daughter's game"      →   Next business morning
Weekend submission               →   Monday 9:00 AM
```

**State Machine:**
```
RECEIVED → EXTRACTED → MAPPED → ROUTED → READY_TO_SEND → SCHEDULED → SENT → ACKNOWLEDGED
    │          │          │        │            │             │         │          │
    └──────────┴──────────┴────────┴────────────┴─────────────┴─────────┴──────────┘
                              State history tracked at each transition
```

```python
# Example usage
from execution_engine import ExecutionEngine

engine = ExecutionEngine()
status, summary = engine.process_submission(extraction, mapped_output, recommendation)

print(summary.headline)      # "The Rusty Anchor → Kevin O'Brien"
print(summary.next_action)   # "Email scheduled for Tuesday, Jan 21 at 1:30 PM"
print(summary.harper_touch_note)  # "Client has dentist appointment Tuesday morning"
```

---

## Project Structure

```
Harper_Prep/
├── extract.py              # Phase 1: Contextual Extraction
├── form_mapper.py          # Phase 2: ACORD Form Mapping
├── routing_engine.py       # Phase 3: Intelligent Routing
├── underwriter_db.py       # Mock underwriter database (10 UWs)
├── execution_engine.py     # Phase 4: Execution & Scheduling
├── transcript.txt          # Sample discovery call transcript
├── demo.html               # Interactive engineering demo
├── test_extract.py         # Phase 1 tests (21 tests)
├── test_form_mapper.py     # Phase 2 tests (29 tests)
├── test_routing_engine.py  # Phase 3 tests
├── test_execution_engine.py # Phase 4 tests
├── pytest.ini              # Test configuration
├── .env                    # API keys (not committed)
└── README.md               # This file
```

---

## Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
pytest -v

# Run specific phase tests
pytest test_extract.py -v           # Phase 1
pytest test_form_mapper.py -v       # Phase 2
pytest test_routing_engine.py -v    # Phase 3
pytest test_execution_engine.py -v  # Phase 4

# Run only unit tests (no API calls)
pytest -v -m "not integration"

# Run integration tests (requires OPENAI_API_KEY)
pytest -v -m "integration"
```

---

## Key Design Decisions

### 1. Context Differentiation
The system explicitly separates historical insurance data from current requirements:

```python
insurance_history = {
    "past_carrier": "Geico",           # Who they HAD
    "past_carrier_context": "personal", # What it was FOR
    "current_need": "specialized business policy"  # What they NEED now
}
```

This prevents the common error of treating a personal auto policy as relevant to a commercial submission.

### 2. No Hallucination Policy
Missing data is never invented. Instead:
- Fields stay `null` in the output
- Missing required fields become **Broker Tasks** with suggested follow-up questions
- Completion percentage is tracked for visibility

### 3. Aarfans Brokerage Touch
Social context is captured separately and used for scheduling:

```python
social_context = {
    "availability_notes": "Unavailable until 1:00 PM Tuesday",
    "personal_constraints": "daughter's dentist appointment",
    "contact_restrictions": "Don't call tomorrow morning"
}
```

This enables "white glove" service where the system respects personal constraints.

### 4. Write Once, Populate Many
Data extracted once is automatically populated across all relevant form sections:

```
Address extracted: "450 Maple Avenue, Charleston, SC 29401"
    ↓
ACORD 125 Applicant Mailing Address: ✓
ACORD 125 Premises Address: ✓
ACORD 126 Location: ✓
```

---

## API Reference

### extract.py
```python
extract_from_transcript(transcript: str) -> DiscoveryCallExtraction
```

### form_mapper.py
```python
map_extraction_to_forms(extraction: DiscoveryCallExtraction) -> MappedFormOutput
```

### routing_engine.py
```python
class RoutingEngine:
    def extract_risk_profile(mapped_output: MappedFormOutput) -> RiskProfile
    def get_recommendations(mapped_output: MappedFormOutput, top_n: int = 3) -> list[RoutingRecommendation]
```

### execution_engine.py
```python
class ExecutionEngine:
    def process_submission(extraction, mapped_output, recommendation) -> tuple[SubmissionStatus, ExecutiveSummary]
```

---

## Demo

Open `demo.html` in a browser for an interactive walkthrough of all 4 phases. The demo shows:

1. **Phase 1:** Raw transcript → Extracted JSON (with highlighted key data)
2. **Phase 2:** Extracted JSON → ACORD form fields + Broker Tasks
3. **Phase 3:** Risk profile → Ranked underwriter recommendations
4. **Phase 4:** Submission status → Executive summary with scheduled action

---

## Future Enhancements

- [ ] Real ACORD PDF generation
- [ ] Email integration for actual sending
- [ ] Vector database for underwriter performance history
- [ ] Multi-turn conversation support
- [ ] Voice-to-text integration for live calls

---

## License

Internal use only - Aarfans Brokerage
