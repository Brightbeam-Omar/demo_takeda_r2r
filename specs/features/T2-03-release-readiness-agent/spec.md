# T2-03 · Release-Readiness Agent (one-day batch release)

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
The lead story for accelerating batch release: for each batch in QA Release, assemble the evidence pack and classify it, with a deterministic checklist making the call.

## Scope
- Deterministic **release checklist** in the site profile (e.g. all tests pass, no OOS, no open deviation, closed deviations reviewed, inbound check passed, no ERP block, no open change control affecting material, CoA present & matching, full-spec tests present when `full_spec`)
- Agent gathers evidence via tools (LIMS results, QMS deviations/change controls, ERP lot/stock, CoA metadata from a new `coa` table in lims_sim), writes a narrative with citations
- Classification is **computed by the checklist**, not the model: `auto_release_candidate` / `needs_review` / `blocked`; model narrative must agree (validator) or proposal is rejected
- QA approves → executor records 'recommended for UD' (does not post UD; system of record unchanged)
- Timer: show 'evidence pack assembled in N seconds' vs a stated manual baseline (configurable)

## Acceptance sketch
- Story batches: one clean candidate, B3150 blocked by open deviation, one needs-review (closed major deviation)
- Validator catches a narrative that claims 'no deviations' when one exists

## Open questions
- Domain SME to define the checklist items and wording; confirm which items are GxP-sensitive phrasing
