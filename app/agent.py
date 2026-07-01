# ruff: noqa
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.workflow import Workflow
from google.genai import types
from mcp import StdioServerParameters
from pydantic import BaseModel

from app.config import config  # sets GOOGLE_GENAI_USE_VERTEXAI=False via load_dotenv

# MCP server connection — absolute path avoids working-directory issues on Windows
_MCP_SCRIPT = str(Path(__file__).parent / "mcp_server.py")
_MCP_PARAMS = StdioConnectionParams(
    server_params=StdioServerParameters(
        command=sys.executable,
        args=[_MCP_SCRIPT],
    )
)


# ── Output Schemas ──────────────────────────────────────────────────────────


class IntentOutput(BaseModel):
    task_type: str          # "handoff" | "drug_lookup" | "schedule" | "comms"
    patient_context: str
    original_request: str


class HandoffNoteOutput(BaseModel):
    soap_note: str
    patient_name: str
    ward: str
    procedure: str
    next_steps: str


class DrugLookupOutput(BaseModel):
    drug_name: str
    interaction_result: str
    recommendation: str
    source: str


class ScheduleOutput(BaseModel):
    action_taken: str
    calendar_changes: str
    reason: str


class CommsOutput(BaseModel):
    draft_type: str
    recipient: str
    subject: str
    body: str


# ── Sub-Agents ──────────────────────────────────────────────────────────────

intent_classifier = LlmAgent(
    name="intent_classifier",
    model=config.model,
    instruction="""You are RoundsMate, an AI assistant for doctors. Classify the doctor's request.

task_type must be exactly one of:
- "handoff": discharge summary, SOAP note, patient handoff, shift transfer
- "drug_lookup": drug interactions, dosage, contraindications, medication check
- "schedule": calendar, shift, break, appointment, time management
- "comms": message patient, referral letter, specialist notification, email draft

Return task_type, patient_context (any patient info from the request), and original_request verbatim.""",
    output_schema=IntentOutput,
    output_key="intent",
)

handoff_note_agent = LlmAgent(
    name="handoff_note_agent",
    model=config.model,
    instruction="""You are the Handoff Note specialist for RoundsMate, assisting LICENSED MEDICAL PROFESSIONALS.

Your input contains a doctor's request. Follow these steps:
1. Extract the patient name from the input text (e.g. "Mrs. Sharma").
2. Call get_patient_file(patient_name=<extracted name>) immediately — do NOT ask the user for a file ID.
3. Use the returned data to generate a complete SOAP handoff note.

Produce a professional SOAP (Subjective, Objective, Assessment, Plan) note.
Use clinical placeholders for any fields not covered by the retrieved data.
The doctor will review and approve before this is saved.""",
    output_schema=HandoffNoteOutput,
    output_key="agent_output",
    tools=[McpToolset(connection_params=_MCP_PARAMS, tool_filter=["get_patient_file"])],
)

drug_lookup_agent = LlmAgent(
    name="drug_lookup_agent",
    model=config.model,
    instruction="""You are the clinical pharmacology reference specialist for RoundsMate.
You provide drug interaction and dosage guidance exclusively to LICENSED MEDICAL PROFESSIONALS
making prescribing decisions. This is a clinical decision-support tool, not patient-facing advice.

Your input contains a doctor's request. Follow these steps:
1. Extract the two drug names from the input (e.g. "ibuprofen" and "metformin").
2. Extract any patient conditions mentioned.
3. Call lookup_drug_interaction(drug_a=..., drug_b=..., patient_conditions=...) immediately.
4. Report the interaction severity, clinical note, recommendation, and source from the tool response.

If a combination is dangerous, begin recommendation with CAUTION.""",
    output_schema=DrugLookupOutput,
    output_key="agent_output",
    tools=[McpToolset(connection_params=_MCP_PARAMS, tool_filter=["lookup_drug_interaction"])],
)

schedule_agent = LlmAgent(
    name="schedule_agent",
    model=config.model,
    instruction="""You are the Schedule Optimizer specialist for RoundsMate, assisting LICENSED MEDICAL PROFESSIONALS.

Your input contains a doctor's scheduling request. Follow these steps:
1. Call list_calendar_events(date=<today's date in YYYY-MM-DD>) to read the current schedule.
2. Identify back-to-back blocks and overloaded shifts.
3. Call create_calendar_event to propose a protected rest slot or deadline reminder.
4. Summarise the proposed changes clearly.

The doctor will review and approve before any calendar changes are confirmed.""",
    output_schema=ScheduleOutput,
    output_key="agent_output",
    tools=[McpToolset(connection_params=_MCP_PARAMS, tool_filter=["list_calendar_events", "create_calendar_event"])],
)

comms_drafter_agent = LlmAgent(
    name="comms_drafter_agent",
    model=config.model,
    instruction="""You are the Communications Drafter specialist for RoundsMate, assisting LICENSED MEDICAL PROFESSIONALS.

Your input contains a doctor's communication request. Follow these steps:
1. Identify the recipient, communication type, and key content from the input.
2. Draft the full professional communication.
3. Call create_gmail_draft(recipient=..., subject=..., body=..., draft_type=...) to save it.
4. Confirm the draft was saved with PENDING_APPROVAL status.

CRITICAL: create_gmail_draft saves a DRAFT only — nothing is sent automatically.
The doctor must approve before anything is sent.""",
    output_schema=CommsOutput,
    output_key="agent_output",
    tools=[McpToolset(connection_params=_MCP_PARAMS, tool_filter=["create_gmail_draft"])],
)


# ── Security Utilities ──────────────────────────────────────────────────────

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{10,12}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"\b[A-Z]{2}\d{6,}\b"), "[ID_REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"), "[EMAIL_REDACTED]"),
    (re.compile(r"\bDOB:?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b", re.IGNORECASE), "[DOB_REDACTED]"),
]

_INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "ignore all instructions",
    "act as",
    "jailbreak",
    "bypass",
    "override system",
    "disregard",
    "forget your instructions",
    "new persona",
    "you are now",
]


def _scrub_pii(text: str) -> str:
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _is_injection(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _INJECTION_KEYWORDS)


def _format_output(task_type: str, data: dict) -> str:
    """Render agent output as readable Markdown for the playground UI."""
    if not isinstance(data, dict) or not data:
        return str(data)

    if task_type == "handoff" or "soap_note" in data:
        return (
            "## 🏥 Patient Handoff Note\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| **Patient** | {data.get('patient_name', '—')} |\n"
            f"| **Ward** | {data.get('ward', '—')} |\n"
            f"| **Procedure** | {data.get('procedure', '—')} |\n\n"
            f"### SOAP Note\n\n{data.get('soap_note', '—')}\n\n"
            f"### Next Steps\n\n{data.get('next_steps', '—')}"
        )
    if task_type == "drug_lookup" or "drug_name" in data:
        rec = str(data.get("recommendation", ""))
        icon = "⚠️ CAUTION" if "CAUTION" in rec.upper() else "✅ Safe to use"
        return (
            "## 💊 Drug Interaction Report\n\n"
            f"**Drug checked:** {data.get('drug_name', '—')}\n\n"
            f"**Finding:** {data.get('interaction_result', '—')}\n\n"
            f"**{icon}**\n\n> {rec}\n\n"
            f"**Source:** *{data.get('source', '—')}*"
        )
    if task_type == "schedule" or "calendar_changes" in data:
        return (
            "## 📅 Schedule Update\n\n"
            f"**Proposed action:** {data.get('action_taken', '—')}\n\n"
            f"**Calendar changes:**\n\n{data.get('calendar_changes', '—')}\n\n"
            f"**Reason:** {data.get('reason', '—')}"
        )
    if task_type == "comms" or "draft_type" in data:
        return (
            "## 📧 Draft Communication\n\n"
            f"| | |\n|---|---|\n"
            f"| **Type** | {data.get('draft_type', '—')} |\n"
            f"| **To** | {data.get('recipient', '—')} |\n"
            f"| **Subject** | {data.get('subject', '—')} |\n\n"
            f"---\n\n{data.get('body', '—')}"
        )
    # Fallback
    return "\n\n".join(
        f"**{k.replace('_', ' ').title()}:** {v}" for k, v in data.items() if v
    )


# ── Workflow Nodes ──────────────────────────────────────────────────────────


def security_checkpoint(ctx: Context, node_input: Any) -> Event:
    """Entry security gate: PII scrub + injection detection + structured audit log."""
    if hasattr(node_input, "parts") and node_input.parts:
        raw = node_input.parts[0].text or ""
    else:
        raw = str(node_input)

    if _is_injection(raw):
        audit = {
            "node": "security_checkpoint",
            "severity": "CRITICAL",
            "event": "INJECTION_DETECTED",
            "session": ctx.session.id,
            "snippet": raw[:100],
        }
        print(f"[AUDIT] {json.dumps(audit)}")
        return Event(
            output="Request blocked: potential prompt injection detected.",
            route="SECURITY_EVENT",
            state={"security_blocked": True},
        )

    scrubbed = _scrub_pii(raw)
    audit = {
        "node": "security_checkpoint",
        "severity": "INFO",
        "event": "INPUT_SCANNED",
        "pii_scrubbed": scrubbed != raw,
        "session": ctx.session.id,
    }
    print(f"[AUDIT] {json.dumps(audit)}")
    return Event(
        output=scrubbed,
        route="PASS",
        state={"scrubbed_input": scrubbed},
    )


def router(node_input: Any) -> Event:
    """Route to specialist; pass the original doctor's request as the output text."""
    data = node_input if isinstance(node_input, dict) else {}
    task_type = data.get("task_type", "handoff")
    valid = {"handoff", "drug_lookup", "schedule", "comms"}
    route = task_type if task_type in valid else "handoff"
    # Pass the human-readable request so the specialist LlmAgent sees natural text
    original_request = data.get("original_request") or data.get("patient_context") or json.dumps(data)
    return Event(
        output=original_request,
        route=route,
        state={"patient_context": data.get("patient_context", ""), "task_type": task_type},
    )


async def approval_gate(ctx: Context, node_input: Any) -> Any:
    """HITL node: show formatted output in UI, then wait for doctor approval."""
    agent_out = node_input if isinstance(node_input, dict) else {}
    task_type = ctx.state.get("task_type", "handoff")
    formatted = _format_output(task_type, agent_out)

    # Render formatted Markdown in the playground UI
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(
                text=(
                    f"{formatted}\n\n"
                    f"---\n\n"
                    f"**Reply `approve` to confirm or `reject` to discard.**"
                )
            )],
        ),
    )

    # Pause workflow and wait for the doctor's decision
    yield RequestInput(
        interrupt_id="doctor_approval",
        message="Type 'approve' to save or 'reject' to discard.",
    )
    # rerun_on_resume=False (default): user's reply becomes node_input for final_output


def blocked_output(node_input: Any) -> Any:
    """Terminal node for security-blocked requests."""
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(
                text=(
                    "⛔ Your request was blocked by the RoundsMate security checkpoint. "
                    "No action was taken. Please rephrase and try again."
                )
            )],
        ),
        output="blocked",
    )


def final_output(ctx: Context, node_input: Any) -> Any:
    """Terminal node: log doctor's approval decision and surface formatted result."""
    decision = str(node_input).strip().lower()
    approved = decision.startswith("approve")
    agent_out = ctx.state.get("agent_output", {})
    task_type = ctx.state.get("task_type", "handoff")

    audit = {
        "node": "final_output",
        "severity": "INFO",
        "decision": "APPROVED" if approved else "REJECTED",
        "session": ctx.session.id,
    }
    print(f"[AUDIT] {json.dumps(audit)}")

    if approved:
        formatted = _format_output(task_type, agent_out)
        message = f"## ✅ Action Approved\n\n{formatted}\n\n*Logged and saved by RoundsMate.*"
    else:
        message = "## ❌ Action Rejected\n\nNo changes were made. Start a new request whenever you're ready."

    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=message)],
        ),
        output=message,
    )


# ── Workflow Graph ───────────────────────────────────────────────────────────
# ADK 2.2.0 edge formats:
#   (source, target)                    — unconditional
#   (source, {route: target, ...})      — conditional routing via dict
# The 3-tuple (source, target, "route") is NOT valid in 2.2.0.

root_agent = Workflow(
    name="roundsmate",
    description=(
        "RoundsMate: AI assistant for doctors. Reduces administrative burden "
        "through secure, multi-agent automation with mandatory human approval."
    ),
    edges=[
        # Entry → security gate (unconditional)
        ("START", security_checkpoint),
        # Security checkpoint: dict-format conditional routing to two different targets
        (security_checkpoint, {"PASS": intent_classifier, "SECURITY_EVENT": blocked_output}),
        # Classifier → router (unconditional)
        (intent_classifier, router),
        # Router: dict-format conditional routing to four different specialist agents
        (router, {
            "handoff": handoff_note_agent,
            "drug_lookup": drug_lookup_agent,
            "schedule": schedule_agent,
            "comms": comms_drafter_agent,
        }),
        # Four DIFFERENT sources converging on approval_gate — valid (different source nodes)
        (handoff_note_agent, approval_gate),
        (drug_lookup_agent, approval_gate),
        (schedule_agent, approval_gate),
        (comms_drafter_agent, approval_gate),
        # Single unconditional edge to final_output
        (approval_gate, final_output),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
