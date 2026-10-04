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
