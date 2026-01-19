# Product Requirements Document: The "Computational Broker" Engine

## 1. Project Overview
**Title:** The "Computational Broker" Engine
**Objective:** Build an intelligent agent that processes raw business discovery call transcripts, extracts structured data for Accord 125/126 forms, and utilizes a simulated "Underwriter Database" to recommend optimal human points of contact based on regional performance metrics.
**Core Philosophy:** Move from "automated" (filling blanks) to "computational" (learning the landscape). The system acts as a "GPS for Insurance," accounting for traffic (market appetite) and weather (risk factors).

---

## 2. Functional Requirements

### Phase 1: Contextual Extraction (The Listener)
**Goal:** Convert noisy conversation transcripts into clean business data.

* **Input Processing:** The system accepts a raw text transcript (approx. 10 minutes) of a discovery call (e.g., a "Corner Tavern" interview).
* **Entity Extraction:** The pipeline identifies and extracts:
    * **Business Entity:** Legal Name, DBA, Physical Address.
    * **Industry Classification:** NAICS/SIC codes derived from business description.
    * **Risk Factors:** Specific hazards (e.g., "live music," "deep fryer," "late hours").
* **Context Differentiation:** The LLM distinguishes between historical data (past providers) and current requirements.
* **Social Context Extraction (Harper Touch):** The system isolates non business constraints, such as client availability (e.g., "Client unavailable until 10:00 AM due to family event").

### Phase 2: Structured Form Mapping (The Architect)
**Goal:** Map extracted data to industry standard schemas without hallucination.

* **Schema Mapping:** The system maps clean data into a JSON structure mirroring Accord 125 (Commercial Insurance Application) and Accord 126 (Commercial Liability) fields.
* **Redundancy Management:** The system applies a "write once, populate many" logic. An address extracted once populates all relevant carrier specific forms.
* **Handling Asymmetry:**
    * If a required field lacks data in the transcript, the system leaves it null.
    * The system flags these missing fields as "Broker Tasks" for follow up.
    * **Strict Constraint:** The agent never hallucinates missing data.

### Phase 3: The Intelligent Routing Engine (The Strategist)
**Goal:** Optimize placement using a data driven recommender system.

* **Underwriter Database:** The system queries a mock database of 10 underwriters containing:
    * Name & Contact Info.
    * Geographic Region (e.g., Southeast, PNW).
    * Risk Appetite (e.g., "Likes Bars," "Avoids Construction").
    * Average Turnaround Time.
    * Recent Performance History (Acceptance/Rejection rates).
* **Recommendation Logic:** The agent selects the best underwriter match based on the extracted risk profile and the underwriter attributes.
* **Justification Output:** The system outputs a rationale for the choice.
    * *Example:* "Recommendation: Melissa (Montgomery). Reason: Averages 2 day turnaround for bars in the Southeast; currently holds high acceptance rate for this NAICS code."

### Phase 4: Human-in-the-Loop & Execution (The Closer)
**Goal:** Manage submission state and timing with "White Glove" logic.

* **Status Manager:** The system tracks submission states (Data Extracted -> Mapped -> Underwriter Selected -> Ready to Send).
* **Temporal Logic:** The system executes actions based on "Social Context."
    * *Example:* If the user is at a game, the system schedules the email for the next business morning.
* **Executive Summary:** The agent generates a concise "Speed of Thought" update summarizing the reasoning, the selected target, and the execution time.

---

## 3. Technical Specifications

### Architecture
* **Modular Design:** Components (Extractor, Mapper, Router) function independently to allow for instant scaling or updates.
* **State Management:** The system utilizes a persistent memory store (or vector store) to retain context from Phase 1 through Phase 4.

### Performance Metrics
* **Accuracy:** Zero hallucination on missing form fields.
* **Reasoning:** Recommendation logic must cite specific database attributes (Speed, Appetite, Region).
* **Speed:** The system processes the "GPS route" (decisions) faster than a human broker can draft an email.