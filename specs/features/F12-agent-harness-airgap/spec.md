# F12 · Agent Harness & Air-Gap Agent

## Context
This is the first working slice of the **orchestration harness**: an agent does the cross-system legwork a QA person does today, inside a deterministic governance boundary (constitution P3). The air-gap case is ideal because **detection is deterministic** (F03 `air_gap`). The agent's job is to **gather and reconcile evidence across ERP, LIMS and QMS and draft the ticket**. A rule validator and a human decide.

## Flow
```
candidates (deterministic: air_gap = true AND no open proposal for row)
  → agent run per candidate: tools (read-only) → model drafts AirGapTicket (structured output)
  → validator (deterministic rules V1–V6) → proposal.status = pending_approval | rejected_by_validator
  → human with role qa_release approves/rejects in UI → on approve: executor renders ticket + email → action_log
  → every step → agent_trace
```

## Functional requirements
| ID | Requirement |
|---|---|
| F12-FR-01 | New service `agents` (FastAPI, port 8200) with DB access to the `app` DB tables `proposal`, `action_log`, `agent_trace`, `audit_event` (writes) and **read-only HTTP** access to app-api, lims-sim, erp-sim and qms-sim. It has no lakehouse mount and no write access to mirror/override tables (separate DB role `agents_rw` with grants only on those 4 tables) |
| F12-FR-02 | `ModelGateway` per `02-architecture` §4 with providers `anthropic` and `replay`. `bedrock` is a stub for T2-10. Settings: `MODEL_ID`, `temperature=0`, `max_tokens=1500`, timeout 60 s, 2 retries. Every call writes `model_request`/`model_response` trace steps with tokens and latency |
| F12-FR-03 | **Replay provider**: key = sha256(agent_key + prompt_version + canonical JSON of tool results + candidate row facts). Recordings live in `services/agents/recordings/<agent>/<key>.json`. Miss → error `ReplayMiss` with the key and a hint to run `make record-agents`. `make record-agents` runs the story scenarios with `anthropic` and writes recordings (committed; synthetic data only) |
| F12-FR-04 | Tools (JSON-schema described, read-only): `get_row(row_key)` (app-api), `get_lims_sample(sample_id)` + `get_lims_results(sample_id)` (lims-sim), `get_erp_lot(prueflos)` (erp-sim), `list_deviations(batch_no)` (qms-sim). Max 8 tool calls per run, otherwise abort with a trace step |
| F12-FR-05 | Prompt files in `services/agents/prompts/air_gap/v1/{system.md, user.md.j2}` with `prompt_version` metadata. The system prompt states the role, the read-only constraint, "cite only evidence returned by tools", and the output schema |
| F12-FR-06 | Output schema `AirGapTicket`: `row_key`, `title` (≤ 90 chars), `summary` (≤ 600 chars), `evidence: [{system: 'ERP'|'LIMS'|'QMS', ref, field, value}]` (≥ 2 items, must include one LIMS approval and one ERP lot item), `hours_in_gap` (int), `open_deviations: [deviation_no]`, `recommended_action` (enum: `post_usage_decision`, `investigate_deviation_first`, `check_interface`), `priority` (`high`,`normal`), `recipient_role` (`qa_release`) |
| F12-FR-07 | **Validator** (deterministic, each rule produces pass/fail + message, stored in `validator_result_json`): **V1** row exists and `air_gap` is still true at validation time · **V2** every evidence item resolves: the referenced record exists and the value matches the source (re-fetched) · **V3** `hours_in_gap` within ±1 of computed · **V4** `recommended_action` equals the rule: `investigate_deviation_first` if any open deviation is linked, else `post_usage_decision` · **V5** `priority = high` iff operative need-by ≤ 14 days away or the row is late, else `normal` · **V6** every identifier pattern (batch, material, sample, lot, deviation) in `title`/`summary` appears in the evidence or the row. Any fail → `rejected_by_validator` (shown in UI with reasons; no human action possible except "re-run") |
| F12-FR-08 | Proposal API: `POST /agents-api/agents/air_gap/run` (admin/qa_release; optional `row_key`, otherwise all candidates) → returns created proposal ids. `GET /agents-api/proposals?status=&agent=`, `GET /agents-api/proposals/{id}`, `POST /agents-api/proposals/{id}/approve` and `/reject {reason}` (role must equal `required_role` or admin). One open proposal per (row_key, kind). **Approve re-runs V1–V6 first; any fail → `rejected_by_validator`.** Approve is idempotent |
| F12-FR-09 | Executor on approve: render (a) a ticket record and (b) an email (subject/body, To: "QA Release Team <qa-release@demo-pharma.example>") from templates. Write `action_log` and set `executed`. **No email is sent**; the UI shows "Sent to outbox (demo)" |
| F12-FR-10 | Identity: the agents service accepts `X-Demo-User` and validates role via app-api `/api/me` (no separate user table) |
| F12-FR-11 | Optional auto-run: if `AGENTS_AUTORUN=true`, the agents service subscribes by polling `/api/sync/status` every 30 s and runs air_gap candidates after each new `contract_run_id`. Default false (presenter clicks "Run") |
| F12-FR-12 | **UI** (built on the F15–F21 shell; F12 depends on F21): `/agents` page with (a) an agent card: name, purpose, model, prompt version, "Run now" button, last run; (b) a Proposals inbox: status tabs, list with row, priority and age; (c) a Proposal detail: summary, evidence table with system icons and "verified ✓" per item from V2, validator checklist V1–V6, Approve/Reject (role-gated), and the executed ticket + email preview; (d) a "View trace" link → `/agents/traces/<trace_id>`: a vertical timeline of steps with expandable payloads, tokens, latency and total cost estimate (tokens × configurable price per 1k in `.env`) |
| F12-FR-13 | The Insights window (F16-FR-09) gains a **Proposal** column showing the agent proposal status with a link to the proposal, and W1 Batch History (F19) shows a proposal-status line. The old alert-band and drawer links are gone |

## Acceptance criteria
- **F12-AC-01** With `LLM_PROVIDER=replay`, after `datagen generate` + `make pipeline` + sync (demo-start state), "Run now" creates a proposal for **B5003** that passes V1–V6, with status `pending_approval`.
- **F12-AC-02** As Pat (planner), Approve → 403. As Alex (qa_release), Approve → `executed`, with action_log, audit_event and an email preview visible.
- **F12-AC-03** Validator unit tests: a crafted output with a wrong evidence value fails V2. Hours off by 3 fails V3. Wrong recommended action when an open deviation exists fails V4. An unknown batch ID in the summary fails V6.
- **F12-AC-04** If the batch gets a UD before approval (ERP event API `POST :8101/events/usage-decision` + `make pipeline` + sync), re-validation on approve fails V1, and the proposal becomes `rejected_by_validator` with message "Air gap resolved".
- **F12-AC-05** The trace for the run shows input → tool calls (≥ 3, across ≥ 2 systems) → model request/response → validation → decision → action, in order.
- **F12-AC-06** Running twice does not create a duplicate open proposal for the same row.
- **F12-AC-07** The agents DB role cannot `INSERT` into `override_value` (integration test expects permission denied).
- **F12-AC-08** With `LLM_PROVIDER=anthropic` and a valid key, the same flow works live (manual check, recorded in the PR).
- **F12-AC-09** A replay miss produces a clear UI error with the hint, not a crash.
