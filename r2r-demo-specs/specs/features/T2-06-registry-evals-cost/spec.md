# T2-06 · Agent Registry, Eval Harness, Cost Meter

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Answer governance and spend concerns: manage agents like people (onboard, observe, retire) and prove accuracy with evals.

## Scope
- Registry table + UI: owner, purpose, tools, model, prompt version, status (draft/active/retired), risk class, approval role, last eval score
- Eval harness `make evals`: golden sets per agent (air-gap 30 cases, release-readiness 50, tacit 100 snippets, briefing 10 Q&A), scorers (exact/structured match, validator pass rate, precision/recall), results stored and shown with trend; CI job runs evals in replay mode
- Promotion gate: an agent version cannot be set `active` unless eval ≥ threshold in profile
- Cost meter: tokens and estimated € per agent per day/run; budget threshold banner

## Acceptance sketch
- Lowering a prompt's quality (fixture) drops the score below threshold and blocks activation
