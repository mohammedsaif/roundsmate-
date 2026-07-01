# RoundsMate — Submission Writeup

## Problem Statement

Doctors in India spend an average of 3 hours per day on administrative paperwork — handoff notes, referral letters, drug lookups, and scheduling — most of it done after clinical hours. This administrative burden contributes directly to burnout, errors in patient handovers, and delayed care.

RoundsMate addresses this with a multi-agent AI system that handles all four administrative task types in a single conversation, with a mandatory human approval gate ensuring nothing is sent, saved, or acted upon without the doctor's explicit confirmation.

---

## Solution Architecture

```
START → security_checkpoint → intent_classifier → router
                                                      ↓
                       ┌──────────┬──────────────┬──────────┐
                  handoff     drug_lookup     schedule    comms
                       │           │               │          │
             handoff_note_   drug_lookup_   schedule_   comms_drafter_
                agent          agent          agent        agent
                  │(Drive)    │(Drug DB)   │(Calendar)  │(Gmail)
                       └──────────┴──────────────┴──────────┘
                                          ↓
                                   approval_gate  ← HITL pause
                                          ↓
                                    final_output
```

The graph is implemented using the **ADK 2.0 Workflow API** (`google.adk.workflow.Workflow`) with function nodes and `{route: target}` dict-format conditional edges.

---

## Concepts Used

| Concept | Where it appears | File |
|---|---|---|
| ADK Workflow graph | Root agent — function nodes + conditional edges | `app/agent.py` |
| LlmAgent | 5 specialist agents with `output_schema` + `output_key` | `app/agent.py` |
| MCP Server | 5 domain tools via FastMCP stdio transport | `app/mcp_server.py` |
| Security Checkpoint | First workflow node — PII scrub + injection detection | `app/agent.py` |
| Human-in-the-Loop | `RequestInput` in `approval_gate` — pauses for doctor decision | `app/agent.py` |
| ctx.state | `task_type`, `patient_context`, `agent_output` shared across nodes | `app/agent.py` |
| Agents CLI | `agents-cli scaffold create`, GEMINI.md, `make playground` | `agents-cli-manifest.yaml` |
| Structured audit log | JSON log on every node decision (INFO/WARNING/CRITICAL) | `app/agent.py` |

---

## Security Design

### 1. PII Scrubbing
Regex patterns applied to every input before any LLM call:
- Phone numbers (10–12 digits) → `[PHONE_REDACTED]`
- National ID format (`AA123456+`) → `[ID_REDACTED]`
- Email addresses → `[EMAIL_REDACTED]`
- Date of birth patterns → `[DOB_REDACTED]`

**Why it matters:** Patient data must not leak into LLM training via API calls. Scrubbing at the entry gate enforces this regardless of what the doctor types.

### 2. Prompt Injection Detection
10 keyword patterns checked before routing (`ignore previous instructions`, `jailbreak`, `act as`, `override system`, etc.). A match routes to `blocked_output` and logs a CRITICAL audit event. No LLM call is made.

**Why it matters:** Medical AI systems are high-value targets for injection attacks that could cause harmful output to reach clinical workflows.

### 3. Mandatory Human Approval Gate
`approval_gate` uses `RequestInput` to pause the entire workflow. The doctor sees a formatted Markdown card of the proposed output and must explicitly type `approve` or `reject`. Nothing is saved, sent, or logged as confirmed without this step.

**Why it matters:** In a clinical context, an auto-acting AI is unacceptable. Every output — whether a drug recommendation or a referral letter — carries medical and legal weight. The approval gate is non-negotiable.

### 4. No Auto-Send in Communications
`create_gmail_draft` saves with `status: "PENDING_APPROVAL"` and never calls a send endpoint. The `comms_drafter_agent` instruction explicitly states: "This is a DRAFT ONLY."

### 5. Structured Audit Log
Every function node logs a JSON event to stdout:
```json
{"node": "security_checkpoint", "severity": "INFO", "event": "INPUT_SCANNED", "pii_scrubbed": true, "session": "abc123"}
```
Severity levels: `INFO` (normal), `WARNING` (anomaly), `CRITICAL` (blocked).

---

## MCP Server Design

File: `app/mcp_server.py` — FastMCP with stdio transport

| Tool | Purpose | Agent |
|---|---|---|
| `get_patient_file(patient_name, file_type)` | Retrieves structured patient record from Drive — vitals, medications, procedure, allergies | handoff_note_agent |
| `lookup_drug_interaction(drug_a, drug_b, patient_conditions)` | Checks drug-drug interaction severity with clinical recommendation and authoritative source citation | drug_lookup_agent |
| `list_calendar_events(date, days_ahead)` | Returns the doctor's shift schedule with back-to-back detection flag | schedule_agent |
| `create_calendar_event(title, date, start_time, duration_minutes, event_type)` | Creates a pending protected-time block or deadline reminder (status: PENDING_APPROVAL) | schedule_agent |
| `create_gmail_draft(recipient, subject, body, draft_type)` | Saves a medical communication draft to Gmail outbox — never sends automatically | comms_drafter_agent |

The MCP server runs as a subprocess via stdio transport. Each specialist agent receives only the tools it needs via `tool_filter`, enforcing least-privilege access.

---

## HITL Flow

1. Doctor sends a request in the playground UI
2. `security_checkpoint` scans and scrubs the input
3. `intent_classifier` classifies the task type
4. `router` routes to the correct specialist agent
5. Specialist agent calls its MCP tool(s) and generates structured output
6. **`approval_gate` pauses** — renders a formatted Markdown card:
   - Handoff: SOAP note table with patient, ward, procedure, next steps
   - Drug: Interaction severity, recommendation, source citation
   - Schedule: Proposed calendar changes with reason
   - Comms: Full draft letter with recipient and subject
7. Doctor reads the card and types `approve` or `reject`
8. `final_output` logs the decision and renders the confirmed result

The HITL gate sits between every specialist agent and every output action. There is no path through the graph that bypasses it.

---

## Demo Walkthrough

Three test cases from the README:

**Case 1 — Handoff Note:** "I need a handoff note for Mrs. Sharma in ward 4, post-appendectomy day 2." → SOAP note card → approve → logged.

**Case 2 — Drug Interaction:** "Check if ibuprofen is safe with metformin for a diabetic patient." → ⚠️ CAUTION card (NSAIDs + metformin risk, WHO EML source) → doctor decides.

**Case 3 — Referral Letter:** "Draft a referral to Dr. Kapoor at cardiology for Mr. Patel, chest pain + elevated troponin." → Draft letter card → approve → saved to Gmail drafts (not sent).

---

## Impact and Value

**Who benefits:** Junior doctors in busy teaching hospitals, where handoff errors are a leading cause of adverse events. Consultants doing back-to-back ward rounds with no admin support.

**What changes:** A task that takes 20–30 minutes per patient (written manually, often after midnight) becomes a 60-second reviewed output. Drug checks that currently involve flipping through a BNF become an instant cited response.

**Why this is safe:** The approval gate means a doctor reviews every single output before it affects a patient. RoundsMate is a decision-support tool, not a decision-making one. The guardrails are architectural, not just instructional.

**Scalability:** The MCP server tools are stubs today (simulated data). Replacing `get_patient_file` with a real Google Drive API call and `lookup_drug_interaction` with a real drug database API requires changing one function each — the agent graph, security model, and HITL flow are unchanged.
