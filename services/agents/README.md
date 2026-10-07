# services/agents

The agent harness (F12): an agent does the cross-system legwork a QA person does today, inside a deterministic
governance boundary (constitution P3). The agent **proposes**; a rule validator and a person decide.

```
candidate rows (air_gap = true, no open proposal)
  -> agent run: read-only tools -> model drafts a ticket (structured output)
  -> validator V1-V6 -> proposal: pending_approval | rejected_by_validator
  -> a person with role qa_release (or admin) approves or rejects -> executor writes the ticket and email
  -> every step goes to agent_trace
```

UI: `/agents` (the agent card and the proposals inbox), `/agents/proposals/:id` (evidence, checklist, decision,
ticket and email), `/agents/traces/:id` (the timeline). The Insights window has a Proposal column and a
**Run air-gap agent** button; the batch drawer has a proposal line.

## Runs offline

`LLM_PROVIDER=replay` (the default, also in every test) answers each model call from a recording. Set
`LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in `.env` to call the model live.

- **Key per model call:** `sha256` of the agent, the prompt version, the turn, the system prompt, the tool specs and
  the message list so far (OQ-139). A recording is only found for the situation it was made in, so recordings are
  valid for the **demo-start state** only. Anything else gives `ReplayMiss`: a 409 whose message names the key and
  says `make record-agents`; the UI shows it, never a crash.
- **Recording:** `make record-agents` runs the agent live for the four demo-start air gaps against a stack in that
  state, writes `recordings/air_gap/<key>.json` (one per call), checks every draft with the validator, and replaces
  the folder only when all four pass. Nothing is written to the database.
- **The key** is read from the environment by the gateway. It is in no trace, recording, log, error text or commit
  (tests assert it).

## The tools (read-only)

`get_row`, `get_lims_sample`, `get_lims_results`, `get_erp_lot`, `list_deviations`: GET requests to allow-listed
hosts, at most 8 calls per run. Each returns a **stable projection** (no freshness, mirror or sync fields) as
canonical JSON, so the same facts always give the same text.

## The evidence-field registry

A ticket may cite only these, and the validator re-reads each from its source (OQ-140). A null is written `none`.

| System | `ref` | Fields |
|---|---|---|
| LIMS | sample id (`S-0000404`) | `status`, `approved_at` |
| ERP | inspection lot (`10000459`) | `ud_code`, `results_recorded_at` |
| QMS | deviation number (`DEV-000039`) | `status` |

Every ticket needs the LIMS `approved_at` and an ERP lot item. The registry is `agents/air_gap/evidence.py`.

## The validator (`agents/air_gap/validator.py`)

| Rule | Checks |
|---|---|
| V1 | the row exists and is still an air gap (otherwise "Air gap resolved") |
| V2 | every evidence item resolves, belongs to this batch, and matches its source |
| V3 | `hours_in_gap` is within 1 h of the hours `r2r_core.airgap` computes from the sources |
| V4 | `recommended_action` and `open_deviations` match QMS (`investigate_deviation_first` iff a linked deviation is open) |
| V5 | `priority` is high iff the need-by is within `agents.air_gap.high_priority_days` (site profile) or the row is late |
| V6 | every batch, material, sample, lot and deviation id in the title and summary is in the evidence or the row |

All rules always run. **Approve runs them again**: a usage decision posted since the draft makes V1 fail and the
proposal `rejected_by_validator`.

## Roles and identity

`X-Demo-User` is forwarded to app-api's `/api/me`, which resolves the role. Reads: every role. Run: `qa_release` or
`admin`. Approve and reject: the proposal's `required_role` (`qa_release`) or `admin`. A refused write leaves a
`forbidden` audit row.

## What the service may write

Only `proposal`, `action_log`, `agent_trace` and `audit_event`, as the Postgres role `agents_rw` (migration
`0014_agents`; password `AGENTS_DB_PASSWORD`). It has no lakehouse mount, and `INSERT` into `override_value` is
"permission denied". The executor renders the ticket record and an email; **nothing is sent** ("Sent to outbox
(demo)").

## Autorun

`AGENTS_AUTORUN=true` polls `/api/sync/status` every 30 s and runs the agent for air-gap rows that never had a
proposal after each new mirrored run. `POST /agents/autorun/pause` and `/resume` (header `X-Scenario-Token`) are for
the demo reset (F13): pause before the wipe, resume after the sync.
