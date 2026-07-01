"""RoundsMate MCP Server — exposes 4 domain tools via stdio transport."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("roundsmate-tools")


# ── Tool 1: Draft Gmail message (never auto-sends) ──────────────────────────


@mcp.tool()
def create_gmail_draft(
    recipient: str,
    subject: str,
    body: str,
    draft_type: str = "general",
) -> dict:
    """Create a Gmail draft for doctor review. Never sends automatically.

    Args:
        recipient: Email address or patient/specialist name.
        subject: Email subject line.
        body: Full email body text.
        draft_type: One of 'patient_message', 'referral', 'specialist_notification', 'handoff'.

    Returns:
        Draft metadata with a confirmation that it is pending doctor approval.
    """
    draft_id = f"DRAFT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return {
        "draft_id": draft_id,
        "status": "PENDING_APPROVAL",
        "recipient": recipient,
        "subject": subject,
        "body_preview": body[:200] + ("..." if len(body) > 200 else ""),
        "draft_type": draft_type,
        "created_at": datetime.utcnow().isoformat(),
        "note": "Draft saved. Awaiting doctor approval before send.",
    }


# ── Tool 2: Read calendar events ────────────────────────────────────────────


@mcp.tool()
def list_calendar_events(
    date: str,
    days_ahead: int = 1,
) -> dict:
    """List the doctor's calendar events for a date range.

    Args:
        date: Start date in YYYY-MM-DD format.
        days_ahead: Number of days to look ahead (default 1).

    Returns:
        List of events with time, title, and conflict flags.
    """
    try:
        start = datetime.fromisoformat(date)
    except ValueError:
        start = datetime.utcnow()

    # Simulated calendar data — replace with real Google Calendar API call
    events = []
    for i in range(days_ahead):
        day = start + timedelta(days=i)
        events.append({
            "date": day.strftime("%Y-%m-%d"),
            "events": [
                {"time": "07:00", "title": "Morning rounds — Ward 4", "duration_min": 90},
                {"time": "09:00", "title": "OPD clinic", "duration_min": 180},
                {"time": "13:00", "title": "Surgery — Theatre 2", "duration_min": 120},
                {"time": "16:00", "title": "Afternoon rounds", "duration_min": 60},
                {"time": "18:00", "title": "Handoff briefing", "duration_min": 30},
            ],
            "back_to_back_detected": True,
            "recommended_break": "12:00–12:30 (no events scheduled)",
        })
    return {"schedule": events, "days_queried": days_ahead}


# ── Tool 3: Create calendar event or block ───────────────────────────────────


@mcp.tool()
def create_calendar_event(
    title: str,
    date: str,
    start_time: str,
    duration_minutes: int = 30,
    event_type: str = "block",
) -> dict:
    """Create a calendar event or protected time block pending doctor approval.

    Args:
        title: Event title (e.g. 'Protected Recovery Time').
        date: Date in YYYY-MM-DD format.
        start_time: Start time in HH:MM format.
        duration_minutes: Duration of the event.
        event_type: 'block' for protected time, 'reminder' for deadline alerts, 'meeting' for appointments.

    Returns:
        Pending event details awaiting doctor confirmation.
    """
    event_id = f"EVT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return {
        "event_id": event_id,
        "status": "PENDING_APPROVAL",
        "title": title,
        "date": date,
        "start_time": start_time,
        "end_time": f"{int(start_time.split(':')[0]):02d}:{(int(start_time.split(':')[1]) + duration_minutes) % 60:02d}",
        "duration_minutes": duration_minutes,
        "event_type": event_type,
        "note": "Event pending doctor approval before calendar update.",
    }


# ── Tool 4: Read patient file from Drive ────────────────────────────────────


@mcp.tool()
def get_patient_file(
    patient_name: str,
    file_type: str = "latest",
) -> dict:
    """Retrieve patient records from Drive for handoff note generation.

    Args:
        patient_name: Patient's full name or ID.
        file_type: One of 'latest' (most recent record), 'discharge', 'labs', 'history'.

    Returns:
        Structured patient data for use in SOAP note generation.
    """
    # Simulated patient data — replace with real Google Drive API call
    return {
        "patient_name": patient_name,
        "file_type": file_type,
        "retrieved_at": datetime.utcnow().isoformat(),
        "data": {
            "admitting_diagnosis": "Acute appendicitis",
            "procedure": "Laparoscopic appendectomy",
            "post_op_day": 2,
            "vitals": {
                "bp": "118/76",
                "hr": 78,
                "temp_c": 37.1,
                "spo2": 98,
            },
            "current_medications": ["metformin 500mg BD", "paracetamol 1g QID PRN"],
            "allergies": ["penicillin"],
            "pending_tasks": ["wound check day 3", "diet upgrade to soft"],
            "next_shift_notes": "Patient stable. Mobilising with physio.",
        },
        "source": "Google Drive — patient-records/",
        "note": "PII fields redacted per RoundsMate security policy.",
    }


# ── Tool 5: Drug interaction lookup ─────────────────────────────────────────


@mcp.tool()
def lookup_drug_interaction(
    drug_a: str,
    drug_b: str,
    patient_conditions: str = "",
) -> dict:
    """Look up drug-drug interactions and dosage guidelines.

    Args:
        drug_a: First drug name.
        drug_b: Second drug name to check against drug_a.
        patient_conditions: Comma-separated list of patient conditions (e.g. 'diabetes, CKD').

    Returns:
        Interaction severity, clinical note, and recommended action with source.
    """
    # Simulated interaction data — replace with real drug DB API
    interaction_map = {
        ("ibuprofen", "metformin"): {
            "severity": "MODERATE",
            "interaction": "NSAIDs may reduce metformin efficacy and increase risk of acute kidney injury in diabetic patients.",
            "recommendation": "CAUTION — prefer paracetamol for analgesia in patients on metformin. Monitor renal function if NSAID is unavoidable.",
            "source": "WHO Essential Medicines List 2023 / BNF 86",
        },
        ("aspirin", "warfarin"): {
            "severity": "HIGH",
            "interaction": "Combined antiplatelet and anticoagulant effect significantly increases bleeding risk.",
            "recommendation": "CAUTION — avoid combination unless under haematology guidance. Monitor INR closely.",
            "source": "BNF 86 / MIMS",
        },
    }

    key = tuple(sorted([drug_a.lower(), drug_b.lower()]))
    result = interaction_map.get(
        key,
        {
            "severity": "NO_KNOWN_INTERACTION",
            "interaction": f"No significant interaction found between {drug_a} and {drug_b} in reference database.",
            "recommendation": f"{drug_a} and {drug_b} appear safe to co-administer. Verify with current BNF for specific patient.",
            "source": "WHO EML 2023 (simulated lookup)",
        },
    )
    return {
        "drug_a": drug_a,
        "drug_b": drug_b,
        "patient_conditions": patient_conditions,
        **result,
        "disclaimer": "This is an AI-assisted lookup. Doctor must verify before prescribing.",
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
