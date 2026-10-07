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

## Runs offline

`LLM_PROVIDER=replay` (the default) answers every model call from a recording in `recordings/`. Set
`LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in `.env` to call the model; `make record-agents` records the demo
state. The key is read only from the environment.

## What the service may write

Only `proposal`, `action_log`, `agent_trace` and `audit_event`, as the Postgres role `agents_rw` (migration
`0014_agents`). It reads app-api, the ERP, LIMS and QMS simulators over HTTP and has no lakehouse mount.
