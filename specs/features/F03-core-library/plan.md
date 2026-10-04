# F03 · Plan
- `packages/r2r_core/src/r2r_core/{profile.py, clock.py, domain.py, sla.py, airgap.py}`.
- `RowFacts`: `row_key, stage_key, lot_type, received_location_type, offsite, current_stage_entry_date, system_need_by_locked, on_hold, ud_rejected, lims_status, ud_effective, ud_code, lims_approved_at`.
- `plan()` algorithm:
  1. `stages = applicable_stages(row)`. `idx = index(current)`. `remaining = stages[idx:]`
  2. `slas = [sla_for(s)]`. `B = sum`
  3. `N = operative_need_by`. If `None`, chain forward from `E`
  4. Otherwise `A = (N − E).days`. If `A ≥ B`, eff = slas. Else, if `A > 0`, eff = `[max(1, round_half_up(s*A/B))]`. Else eff = `[1]*len`
  5. `must_complete_by[last] = N`, then walk backwards subtracting eff of the following stage
  6. `expected = must_complete_by[current]`. Then RAG, late and the auto reason
- Use `decimal` for `round_half_up`. Dates are `datetime.date` only. Python's `round` must not be used (it is banker's rounding).
- The `HttpClock` uses `httpx` with a 300 ms timeout.

## Deviations
- **Decisions OQ-017 to OQ-023** are recorded in `specs/OPEN_QUESTIONS.md` and implemented as decided: safe `applies_if` mini-evaluator (`applies_if.py`), SLA-bearing stages are those with `sla_days > 0` that are not terminal, clock contract (`CLOCK_*` env vars, `psycopg`), profile lookup (`SITE_PROFILES_DIR`, then walking up), `extra="forbid"`, `Flags`, tuple sort key, `StageKey` as a `NewType`.
- **Choices not covered by an OQ:**
  - When `available <= 0` the result has `compressed = True` (every stage is squeezed to the 1-day floor) and `compression_ratio = None`. With no compression, `compression_ratio` is also `None`.
  - A started (SLA-bearing) stage with no entry date returns a result with no expected completion and no RAG, instead of raising.
  - `days_in_stage` is computed whenever an entry date exists, for any stage.
  - `air_gap` returns whole hours elapsed (floor). It returns `0` hours when the lot is not approved, has no approval time, or the approval is in the future.
  - The sort key is `(group, expected ordinal or max, material_no, batch_no)`. Days remaining and expected completion order identically for a given "today", so no separate overdue field is needed.
  - `from` in `period` never excludes a row (overdue rows roll in), as 03 section 5.6 says.
- **Tooling:** ruff ignores E501 under `tests/` (worked-example tables), `types-pyyaml` is a dev dependency, and `make coverage-core` is called from `make check` (OQ-023).
- **Test naming:** `test_f03_acNN_<what>` (OQ-023). The `test-writer` agent file in `.claude/agents/` uses a different pattern (`test_ac_<id>_<nn>`) and is not registered in this session, so tests were written directly.
- **Integration test:** `tests/integration/test_db_clock.py` runs `DbClock` against a real Postgres in a scratch schema. It could not be run on the dev machine (no Docker or Postgres); the CI `integration` job runs it.

