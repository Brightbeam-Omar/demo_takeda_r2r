# F12 · Plan
- `services/agents/src/agents/{main.py, gateway/{base.py, anthropic.py, replay.py, bedrock.py}, tools/{registry.py, app.py, lims.py, erp.py, qms.py}, harness/{runner.py, trace.py, proposals.py, executor.py}, air_gap/{candidates.py, schema.py, validator.py, agent.py}, prompts/, templates/}`.
- The runner is a generic loop: build messages → model call with tools → execute tool calls (registry enforces read-only, allow-listed hosts) → repeat until a final structured output or the limit → parse with Pydantic → validator → persist. It is generic so T2 agents plug in with a schema + validator + prompt.
- Anthropic: use the official `anthropic` SDK with tool use. Structured output: final tool `submit_ticket` whose input schema is `AirGapTicket`.
- Validator re-fetches sources itself (never trusts tool results cached in the run), so V2 is independent verification.
- DB role created in an app migration: `agents_rw` with `INSERT, SELECT, UPDATE` on `proposal`, `action_log` and `agent_trace`, and `INSERT` on `audit_event` only.

## Deviations
