# T2-08 · Value Calculator

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Embedded, transparent business-case calculator for the conversation with budget holders.

## Scope
- Inputs: batches/yr, avg batch value, failed/reworked batch rate and share avoidable, QC dwell days and reduction, inventory in QC, carrying rate, manual hours/yr and realisation %, hourly cost, expedites avoided × fee, build cost, run cost
- Outputs: annual benefit by lever (tiered certain → speculative), payback, 5-yr NPV at chosen rate, 'one saved batch covers X% of build' line, sensitivity toggles
- All formulas shown (explainable), defaults generic; no reference-client figures unless approved

## Acceptance sketch
- Formula unit tests; exported PDF/CSV of a scenario

## Open questions
- Which reference figures may be quoted (commercial decision, outside engineering)
