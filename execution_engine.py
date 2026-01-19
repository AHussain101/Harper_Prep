"""
Phase 4: Execution Engine (The Closer)
Human-in-the-Loop & Execution for the Computational Broker Engine

This module orchestrates the final phase of the submission workflow:
- Tracks submission state through the pipeline
- Schedules actions based on social context (Harper Touch)
- Generates executive summaries for brokers
- Manages the human-in-the-loop approval process
"""

import re
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from extract import DiscoveryCallExtraction, SocialContext
from form_mapper import MappedFormOutput
from routing_engine import RoutingRecommendation, RiskProfile


# =============================================================================
# 1. SUBMISSION STATE MANAGER
# =============================================================================

class SubmissionState(str, Enum):
    """Tracks submission through the pipeline"""
    RECEIVED = "received"
    EXTRACTED = "extracted"           # Phase 1 complete
    MAPPED = "mapped"                 # Phase 2 complete
    ROUTED = "routed"                 # Phase 3 complete
    READY_TO_SEND = "ready_to_send"   # Approved, waiting for schedule
    SCHEDULED = "scheduled"           # Email scheduled
    SENT = "sent"                     # Email sent
    ACKNOWLEDGED = "acknowledged"     # Underwriter acknowledged


class SubmissionStatus(BaseModel):
    """Complete status of a submission"""
    submission_id: str = Field(description="Unique identifier for the submission")
    business_name: str = Field(description="Name of the business being submitted")
    current_state: SubmissionState = Field(description="Current state in the pipeline")
    state_history: list[dict] = Field(
        default_factory=list,
        description="History of state changes [{state, timestamp, notes}]"
    )
    created_at: datetime = Field(description="When the submission was created")
    updated_at: datetime = Field(description="When the submission was last updated")
    scheduled_send_time: Optional[datetime] = Field(
        None,
        description="Scheduled time for sending to underwriter"
    )
    recommended_underwriter: Optional[str] = Field(
        None,
        description="Name of the recommended underwriter"
    )
    broker_tasks_pending: int = Field(
        0,
        description="Number of follow-up tasks still pending"
    )


# =============================================================================
# 2. TEMPORAL SCHEDULER (Harper Touch Logic)
# =============================================================================

class TemporalScheduler:
    """
    Schedules actions based on social context (Harper Touch).

    Implements intelligent scheduling that respects client availability,
    personal constraints, and business hours.
    """

    # Business hours configuration
    BUSINESS_START_HOUR = 9   # 9 AM
    BUSINESS_END_HOUR = 17    # 5 PM
    BUSINESS_DAYS = {0, 1, 2, 3, 4}  # Monday through Friday

    # Day name mappings
    DAY_NAMES = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
        'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6
    }

    def parse_availability(self, social_context: SocialContext) -> dict:
        """
        Parse availability from social context into structured format.

        Args:
            social_context: The social context from extraction

        Returns:
            Dictionary with:
            - available_after: datetime when client becomes available
            - restrictions: list of time restrictions
            - notes: human-readable notes about availability
        """
        now = datetime.now()
        available_after = now
        restrictions = []
        notes = ""

        if not social_context:
            return {
                "available_after": available_after,
                "restrictions": restrictions,
                "notes": "No availability constraints specified"
            }

        # Parse availability notes
        availability_text = social_context.availability_notes or ""
        restrictions_text = social_context.contact_restrictions or ""
        constraints_text = social_context.personal_constraints or ""

        combined_text = f"{availability_text} {restrictions_text} {constraints_text}".lower()

        # Parse "unavailable until [day] [time]" patterns
        until_pattern = r"unavailable until\s+(\w+)(?:\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?|until\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+(\w+)"
        until_match = re.search(until_pattern, combined_text)

        if until_match:
            groups = until_match.groups()
            if groups[0]:  # "unavailable until [day] [time]" format
                day_name = groups[0]
                hour = int(groups[1]) if groups[1] else 9
                minute = int(groups[2]) if groups[2] else 0
                am_pm = groups[3]
            elif groups[4]:  # "until [time] [day]" format
                day_name = groups[7] if groups[7] else None
                hour = int(groups[4])
                minute = int(groups[5]) if groups[5] else 0
                am_pm = groups[6]
            else:
                day_name = None
                hour = 9
                minute = 0
                am_pm = None

            # Convert 12-hour to 24-hour if needed
            if am_pm == 'pm' and hour < 12:
                hour += 12
            elif am_pm == 'am' and hour == 12:
                hour = 0

            # Calculate the target date
            if day_name and day_name in self.DAY_NAMES:
                target_weekday = self.DAY_NAMES[day_name]
                days_ahead = target_weekday - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now + timedelta(days=days_ahead)
                available_after = target_date.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                restrictions.append(f"Unavailable until {day_name.capitalize()} {hour}:{minute:02d}")

        # Parse "don't call tomorrow morning" pattern
        tomorrow_pattern = r"don'?t\s+(?:call|contact)?\s*tomorrow\s*(morning|afternoon|evening)?"
        tomorrow_match = re.search(tomorrow_pattern, combined_text)

        if tomorrow_match:
            time_of_day = tomorrow_match.group(1)
            tomorrow = now + timedelta(days=1)

            if time_of_day == 'morning':
                # Morning is before noon, so schedule for afternoon
                available_after = tomorrow.replace(hour=13, minute=0, second=0, microsecond=0)
                restrictions.append("No contact tomorrow morning")
            elif time_of_day == 'afternoon':
                # Afternoon is after noon, so schedule for next day
                available_after = (tomorrow + timedelta(days=1)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                )
                restrictions.append("No contact tomorrow afternoon")
            else:
                # Generic "don't call tomorrow" - schedule for day after
                available_after = (tomorrow + timedelta(days=1)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                )
                restrictions.append("No contact tomorrow")

        # Parse "next week" pattern
        if "next week" in combined_text:
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_monday = now + timedelta(days=days_until_monday)
            available_after = next_monday.replace(hour=9, minute=0, second=0, microsecond=0)
            restrictions.append("Prefers contact next week")

        # Build notes from personal constraints
        if social_context.personal_constraints:
            notes = social_context.personal_constraints
        elif social_context.availability_notes:
            notes = social_context.availability_notes

        return {
            "available_after": available_after,
            "restrictions": restrictions,
            "notes": notes
        }

    def get_next_business_window(self, after_time: datetime) -> datetime:
        """
        Find next valid business hour window (9 AM - 5 PM, Mon-Fri).

        Args:
            after_time: The time after which to find the next window

        Returns:
            datetime of the next valid business window
        """
        result = after_time

        # If before business hours on a business day, move to start of business hours
        if result.weekday() in self.BUSINESS_DAYS:
            if result.hour < self.BUSINESS_START_HOUR:
                result = result.replace(
                    hour=self.BUSINESS_START_HOUR,
                    minute=0,
                    second=0,
                    microsecond=0
                )
                return result
            elif result.hour >= self.BUSINESS_END_HOUR:
                # After business hours, move to next business day
                result = result + timedelta(days=1)
                result = result.replace(
                    hour=self.BUSINESS_START_HOUR,
                    minute=0,
                    second=0,
                    microsecond=0
                )

        # If weekend, move to Monday
        while result.weekday() not in self.BUSINESS_DAYS:
            result = result + timedelta(days=1)

        # Ensure we're in business hours
        if result.hour < self.BUSINESS_START_HOUR:
            result = result.replace(
                hour=self.BUSINESS_START_HOUR,
                minute=0,
                second=0,
                microsecond=0
            )
        elif result.hour >= self.BUSINESS_END_HOUR:
            result = result + timedelta(days=1)
            while result.weekday() not in self.BUSINESS_DAYS:
                result = result + timedelta(days=1)
            result = result.replace(
                hour=self.BUSINESS_START_HOUR,
                minute=0,
                second=0,
                microsecond=0
            )

        return result

    def schedule_action(
        self,
        social_context: SocialContext,
        action_type: str
    ) -> dict:
        """
        Schedule an action respecting client availability.

        Args:
            social_context: Client's social context with availability info
            action_type: Type of action to schedule (e.g., "email", "call")

        Returns:
            Dictionary with:
            - scheduled_time: datetime when action is scheduled
            - reason: explanation for the scheduled time
            - respects_constraint: what constraint was respected
        """
        # Parse availability constraints
        availability = self.parse_availability(social_context)
        available_after = availability["available_after"]
        restrictions = availability["restrictions"]
        notes = availability["notes"]

        # Add a small buffer (30 minutes) after availability time
        buffer_time = available_after + timedelta(minutes=30)

        # Find next business window
        scheduled_time = self.get_next_business_window(buffer_time)

        # Build reason
        if restrictions:
            reason = f"Scheduled after availability window. {'; '.join(restrictions)}"
            respects_constraint = restrictions[0] if restrictions else "Business hours"
        else:
            reason = "Scheduled within standard business hours"
            respects_constraint = "Business hours (9 AM - 5 PM, Mon-Fri)"

        # Add personal context if available
        if notes:
            reason += f". Client note: {notes}"

        return {
            "scheduled_time": scheduled_time,
            "reason": reason,
            "respects_constraint": respects_constraint
        }


# =============================================================================
# 3. EXECUTIVE SUMMARY GENERATOR
# =============================================================================

class ExecutiveSummary(BaseModel):
    """Speed of Thought summary for broker"""
    headline: str = Field(description="One-line summary of the submission")
    business_snapshot: str = Field(description="2-3 sentences about the business")
    routing_rationale: str = Field(description="Why this underwriter was selected")
    next_action: str = Field(description="What happens next and when")
    broker_tasks: list[str] = Field(
        default_factory=list,
        description="Outstanding follow-up tasks"
    )
    harper_touch_note: str = Field(
        description="Client availability and preferences"
    )
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="When the summary was generated"
    )


class ExecutiveSummaryGenerator:
    """Generates 'Speed of Thought' executive summaries"""

    def generate_summary(
        self,
        extraction: DiscoveryCallExtraction,
        mapped_output: MappedFormOutput,
        recommendation: RoutingRecommendation,
        scheduled_time: datetime,
        status: SubmissionStatus
    ) -> ExecutiveSummary:
        """
        Generate concise executive summary for broker review.

        Args:
            extraction: Phase 1 extraction output
            mapped_output: Phase 2 mapped form output
            recommendation: Phase 3 routing recommendation
            scheduled_time: Scheduled action time from Phase 4
            status: Current submission status

        Returns:
            ExecutiveSummary with all key information
        """
        # Generate headline
        headline = self._generate_headline(extraction, recommendation)

        # Generate business snapshot
        business_snapshot = self._generate_business_snapshot(extraction, mapped_output)

        # Generate routing rationale
        routing_rationale = self._generate_routing_rationale(recommendation)

        # Generate next action
        next_action = self._generate_next_action(scheduled_time, extraction)

        # Extract broker tasks
        broker_tasks = self._extract_broker_tasks(mapped_output)

        # Generate Harper Touch note
        harper_touch_note = self._generate_harper_touch_note(extraction)

        return ExecutiveSummary(
            headline=headline,
            business_snapshot=business_snapshot,
            routing_rationale=routing_rationale,
            next_action=next_action,
            broker_tasks=broker_tasks,
            harper_touch_note=harper_touch_note,
            generated_at=datetime.now()
        )

    def _generate_headline(
        self,
        extraction: DiscoveryCallExtraction,
        recommendation: RoutingRecommendation
    ) -> str:
        """Generate one-line headline summary."""
        business_name = extraction.business_entity.dba or extraction.business_entity.legal_name or "Unknown Business"
        underwriter_name = recommendation.recommended_underwriter.name

        # Add specialty note if available
        specialties = getattr(recommendation.recommended_underwriter, 'naics_specialties', [])
        if specialties and extraction.industry_classification.naics_code in specialties:
            industry = extraction.industry_classification.business_description or "Industry"
            return f"{business_name} -> {underwriter_name} ({industry} Specialist)"

        return f"{business_name} -> {underwriter_name}"

    def _generate_business_snapshot(
        self,
        extraction: DiscoveryCallExtraction,
        mapped_output: MappedFormOutput
    ) -> str:
        """Generate 2-3 sentence business description."""
        parts = []

        # Business type and location
        business_desc = extraction.industry_classification.business_description or "Business"
        location = ""
        if extraction.business_entity.address:
            addr = extraction.business_entity.address
            if addr.city and addr.state:
                location = f" in {addr.city}, {addr.state}"
        parts.append(f"{business_desc}{location}.")

        # Revenue and composition
        revenue_parts = []
        if extraction.revenue_details.gross_annual_sales:
            revenue = extraction.revenue_details.gross_annual_sales
            if revenue >= 1_000_000:
                revenue_str = f"${revenue/1_000_000:.1f}M"
            else:
                revenue_str = f"${revenue/1_000:.0f}K"
            revenue_parts.append(f"{revenue_str} revenue")

        if extraction.revenue_details.alcohol_percentage:
            revenue_parts.append(f"{extraction.revenue_details.alcohol_percentage:.0f}% alcohol")

        if revenue_parts:
            parts.append(", ".join(revenue_parts) + ".")

        # Special features/hazards
        special_features = []
        if extraction.risk_factors.hazards:
            # Look for entertainment-related hazards
            for hazard in extraction.risk_factors.hazards:
                hazard_lower = hazard.lower()
                if any(word in hazard_lower for word in ['piano', 'music', 'band', 'entertainment', 'live']):
                    special_features.append(hazard)
                    break

        if mapped_output.accord_126.liquor_liability.liquor_liability_required:
            special_features.append("Liquor liability required")

        if special_features:
            parts.append(" ".join(special_features) + ".")

        return " ".join(parts)

    def _generate_routing_rationale(
        self,
        recommendation: RoutingRecommendation
    ) -> str:
        """Generate routing rationale."""
        underwriter = recommendation.recommended_underwriter
        parts = [f"{underwriter.name} selected."]

        # Add specialization info
        reasons = []
        if hasattr(underwriter, 'naics_specialties') and underwriter.naics_specialties:
            naics = underwriter.naics_specialties[0] if underwriter.naics_specialties else ""
            reasons.append(f"Specializes in NAICS {naics}")

        if hasattr(underwriter, 'regions') and underwriter.regions:
            regions = ", ".join(underwriter.regions[:2])
            reasons.append(f"{regions} region")

        if reasons:
            parts.append(" ".join(reasons) + ".")

        # Add performance metrics
        metrics = []
        if hasattr(underwriter, 'avg_turnaround_days'):
            metrics.append(f"{underwriter.avg_turnaround_days}-day avg turnaround")
        if hasattr(underwriter, 'acceptance_rate'):
            metrics.append(f"{underwriter.acceptance_rate}% acceptance rate")

        if metrics:
            parts.append(", ".join(metrics) + ".")

        return " ".join(parts)

    def _generate_next_action(
        self,
        scheduled_time: datetime,
        extraction: DiscoveryCallExtraction
    ) -> str:
        """Generate next action description."""
        # Format the scheduled time nicely
        time_str = scheduled_time.strftime("%A, %b %d at %I:%M %p")

        action = f"Email scheduled for {time_str}"

        # Add constraint context if available
        if extraction.social_context:
            if extraction.social_context.contact_restrictions:
                action += f" (Respecting: {extraction.social_context.contact_restrictions})"
            elif extraction.social_context.availability_notes:
                action += f" (Client: {extraction.social_context.availability_notes})"

        return action

    def _extract_broker_tasks(self, mapped_output: MappedFormOutput) -> list[str]:
        """Extract pending broker tasks as simple strings."""
        tasks = []

        for task in mapped_output.broker_tasks.tasks:
            if task.suggested_question:
                tasks.append(task.suggested_question)
            else:
                # Convert field name to readable format
                field_name = task.field_name.replace(".", " ").replace("_", " ")
                tasks.append(f"Obtain {field_name}")

        return tasks

    def _generate_harper_touch_note(
        self,
        extraction: DiscoveryCallExtraction
    ) -> str:
        """Generate Harper Touch note about client preferences."""
        if not extraction.social_context:
            return "No specific availability constraints noted."

        parts = []
        ctx = extraction.social_context

        if ctx.personal_constraints:
            parts.append(ctx.personal_constraints)

        if ctx.preferred_contact_time:
            parts.append(f"Prefers {ctx.preferred_contact_time} contact")

        if ctx.contact_restrictions:
            parts.append(ctx.contact_restrictions)

        if ctx.availability_notes and ctx.availability_notes not in " ".join(parts):
            parts.append(ctx.availability_notes)

        if parts:
            return ". ".join(parts)

        return "No specific availability constraints noted."


# =============================================================================
# 4. EXECUTION ENGINE (Main Orchestrator)
# =============================================================================

class ExecutionEngine:
    """
    Orchestrates the complete submission workflow.

    This is the main orchestrator for Phase 4, coordinating:
    - Submission state management
    - Temporal scheduling
    - Executive summary generation
    - Human-in-the-loop approval tracking
    """

    def __init__(self):
        """Initialize the execution engine."""
        self.scheduler = TemporalScheduler()
        self.summary_generator = ExecutiveSummaryGenerator()
        self.submissions: dict[str, SubmissionStatus] = {}

    def process_submission(
        self,
        extraction: DiscoveryCallExtraction,
        mapped_output: MappedFormOutput,
        recommendation: RoutingRecommendation
    ) -> tuple[SubmissionStatus, ExecutiveSummary]:
        """
        Process a complete submission through Phase 4.

        Args:
            extraction: Phase 1 extraction output
            mapped_output: Phase 2 mapped form output
            recommendation: Phase 3 routing recommendation

        Returns:
            Tuple of (SubmissionStatus, ExecutiveSummary)
        """
        # Create submission ID
        submission_id = str(uuid.uuid4())[:8].upper()

        # Get business name
        business_name = (
            extraction.business_entity.dba or
            extraction.business_entity.legal_name or
            "Unknown Business"
        )

        # Create initial status
        now = datetime.now()
        status = SubmissionStatus(
            submission_id=submission_id,
            business_name=business_name,
            current_state=SubmissionState.ROUTED,
            state_history=[
                {"state": SubmissionState.RECEIVED.value, "timestamp": now.isoformat(), "notes": "Submission received"},
                {"state": SubmissionState.EXTRACTED.value, "timestamp": now.isoformat(), "notes": "Phase 1 complete"},
                {"state": SubmissionState.MAPPED.value, "timestamp": now.isoformat(), "notes": "Phase 2 complete"},
                {"state": SubmissionState.ROUTED.value, "timestamp": now.isoformat(), "notes": "Phase 3 complete"}
            ],
            created_at=now,
            updated_at=now,
            recommended_underwriter=recommendation.recommended_underwriter.name,
            broker_tasks_pending=len(mapped_output.broker_tasks.tasks)
        )

        # Schedule action based on social context
        schedule_result = self.scheduler.schedule_action(
            extraction.social_context,
            "email"
        )
        scheduled_time = schedule_result["scheduled_time"]

        # Update status with scheduled time
        status.scheduled_send_time = scheduled_time
        self.update_state(
            status.submission_id,
            SubmissionState.SCHEDULED,
            f"Scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')}"
        )
        status.current_state = SubmissionState.SCHEDULED

        # Store submission
        self.submissions[submission_id] = status

        # Generate executive summary
        summary = self.summary_generator.generate_summary(
            extraction=extraction,
            mapped_output=mapped_output,
            recommendation=recommendation,
            scheduled_time=scheduled_time,
            status=status
        )

        return status, summary

    def update_state(
        self,
        submission_id: str,
        new_state: SubmissionState,
        notes: str = ""
    ) -> None:
        """
        Update submission state with history tracking.

        Args:
            submission_id: ID of the submission to update
            new_state: New state to transition to
            notes: Optional notes about the state change
        """
        if submission_id in self.submissions:
            status = self.submissions[submission_id]
            status.current_state = new_state
            status.updated_at = datetime.now()
            status.state_history.append({
                "state": new_state.value,
                "timestamp": datetime.now().isoformat(),
                "notes": notes
            })

    def get_pending_actions(self) -> list[dict]:
        """
        Get all scheduled actions that are due.

        Returns:
            List of pending actions with submission details
        """
        now = datetime.now()
        pending = []

        for submission_id, status in self.submissions.items():
            if (status.current_state == SubmissionState.SCHEDULED and
                status.scheduled_send_time and
                status.scheduled_send_time <= now):
                pending.append({
                    "submission_id": submission_id,
                    "business_name": status.business_name,
                    "scheduled_time": status.scheduled_send_time,
                    "recommended_underwriter": status.recommended_underwriter,
                    "action": "send_email"
                })

        return pending


# =============================================================================
# 5. MAIN FUNCTION
# =============================================================================

def main():
    """
    Main entry point - demonstrates the complete 4-phase pipeline.

    1. Loads transcript.txt
    2. Runs Phase 1 extraction
    3. Runs Phase 2 mapping
    4. Runs Phase 3 routing
    5. Runs Phase 4 execution (scheduling + summary)
    6. Prints the complete executive summary
    """
    import json

    print("=" * 70)
    print("COMPUTATIONAL BROKER ENGINE")
    print("Phase 4: Execution Engine (The Closer)")
    print("=" * 70)
    print()

    # Load transcript
    print("[1] Loading transcript...")
    try:
        with open("transcript.txt", "r") as f:
            transcript = f.read()
        print(f"    Loaded transcript ({len(transcript)} characters)")
    except FileNotFoundError:
        print("    ERROR: transcript.txt not found")
        print("    Please ensure transcript.txt exists in the current directory")
        return

    # Phase 1: Extract
    print("\n[2] Running Phase 1: Contextual Extraction...")
    try:
        from extract import extract_from_transcript
        extraction = extract_from_transcript(transcript)
        print("    Extraction complete")
    except ImportError as e:
        print(f"    ERROR: Could not import from extract module: {e}")
        return
    except Exception as e:
        print(f"    ERROR during extraction: {e}")
        return

    # Phase 2: Map
    print("\n[3] Running Phase 2: Form Mapping...")
    try:
        from form_mapper import map_extraction_to_forms
        mapped_output = map_extraction_to_forms(extraction)
        print("    Form mapping complete")
    except ImportError as e:
        print(f"    ERROR: Could not import from form_mapper module: {e}")
        return
    except Exception as e:
        print(f"    ERROR during form mapping: {e}")
        return

    # Phase 3: Route
    print("\n[4] Running Phase 3: Intelligent Routing...")
    try:
        from routing_engine import RoutingEngine
        routing_engine = RoutingEngine()
        recommendations = routing_engine.get_recommendations(mapped_output, top_n=3)
        primary_recommendation = recommendations[0]
        print("    Routing complete")
    except ImportError as e:
        print(f"    ERROR: Could not import from routing_engine module: {e}")
        return
    except Exception as e:
        print(f"    ERROR during routing: {e}")
        return

    # Phase 4: Execute
    print("\n[5] Running Phase 4: Execution & Scheduling...")
    engine = ExecutionEngine()
    status, summary = engine.process_submission(
        extraction=extraction,
        mapped_output=mapped_output,
        recommendation=primary_recommendation
    )
    print("    Execution complete")

    # Print Executive Summary
    print("\n")
    print("=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)
    print()

    print(f"HEADLINE: {summary.headline}")
    print()

    print(f"BUSINESS: {summary.business_snapshot}")
    print()

    print(f"ROUTING: {summary.routing_rationale}")
    print()

    print(f"NEXT ACTION: {summary.next_action}")
    print()

    if summary.broker_tasks:
        print("BROKER TASKS:")
        for task in summary.broker_tasks:
            print(f"  - {task}")
    else:
        print("BROKER TASKS: None - all required information collected")
    print()

    print(f"HARPER TOUCH: {summary.harper_touch_note}")
    print()

    print("=" * 70)
    print("SUBMISSION STATUS")
    print("=" * 70)
    print(f"  Submission ID: {status.submission_id}")
    print(f"  Current State: {status.current_state.value}")
    print(f"  Recommended Underwriter: {status.recommended_underwriter}")
    print(f"  Scheduled Send Time: {status.scheduled_send_time.strftime('%Y-%m-%d %H:%M') if status.scheduled_send_time else 'Not scheduled'}")
    print(f"  Pending Tasks: {status.broker_tasks_pending}")
    print()

    print("State History:")
    for entry in status.state_history:
        print(f"  - {entry['state']}: {entry['notes']}")

    print()
    print("=" * 70)
    print("Phase 4 Complete - Submission ready for broker review")
    print("=" * 70)

    return status, summary


if __name__ == "__main__":
    main()
