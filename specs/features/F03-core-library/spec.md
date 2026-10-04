# F03 · Core Library: Site Profile, Demo Clock, SLA Maths

## Context
`packages/r2r_core` holds the logic shared by every service. Its SLA maths **is the business logic** of the demo and must match `03-domain-model.md` §5 exactly.

## Functional requirements
| ID | Requirement |
|---|---|
| F03-FR-01 | `profile.py`: Pydantic models for the YAML in `03-domain-model` §2. `load_profile(name_or_path)` resolves `config/site-profiles/<name>.yaml`. Validation: stage keys unique; exactly one terminal stage; metric stage keys exist (or `stage: null` with an explicit `sla_days`); `reeval_sla_overrides` keys exist; reason codes non-empty |
| F03-FR-02 | Ship `config/site-profiles/site_a.yaml` exactly as in the domain model |
| F03-FR-03 | `clock.py`: `now()`, `today(tz)` and `set_clock_source(source)`. Sources: `FixedClock(dt)` (tests), `DbClock(dsn)` (reads `demo_clock`), `HttpClock(url)` (scenario service, 1 s cache, falls back to `DbClock`). The default source comes from env `CLOCK_SOURCE=http|db|fixed` |
| F03-FR-04 | `domain.py`: enums `StageKey` (dynamic from the profile at runtime, with a static string type), `LotType`, `Rag`, `Role`, `OverrideField`; dataclass `RowFacts` (fields needed by the SLA maths, see plan) |
| F03-FR-05 | `sla.py` pure functions: `applicable_stages(row, profile)`, `sla_for(stage, lot_type, profile)`, `operative_need_by(row, adjusted)`, `plan(row, profile, today, adjusted: AdjustedNeedBy | None) -> PlanResult` (`AdjustedNeedBy(date, reason_code)`) returning `expected_completion`, `must_complete_by` per remaining stage, `compressed: bool`, `compression_ratio`, `effective_slas`, `days_in_stage`, `days_remaining`, `rag`, `late`, `late_reason_auto` |
| F03-FR-06 | `sla.py`: `exception_sort_key(row, plan, flags)` implementing `03-domain-model` §5.5 |
| F03-FR-07 | `sla.py`: `in_period(plan, stage_terminal, period)` implementing §5.6 |
| F03-FR-08 | `airgap.py`: `air_gap(lims_status, ud_code, lims_approved_at, now, threshold_hours, erp_results_recorded_at=None) -> (bool, hours)`. True only when `ud_code IS NULL` and `erp_results_recorded_at` is None |
| F03-FR-09 | 100% branch coverage on `sla.py` and `airgap.py` (enforced by `make coverage-core`, which runs `pytest --cov-branch --cov-fail-under=100` on those two modules only and is called from `make check`) |

## Acceptance criteria
Each case is covered by a test named `test_f03_acNN_<what>` (parametrised where useful), consistent with F01 and F02. The profile is `site_a`, and today is `2026-10-12` unless stated otherwise.
- **F03-AC-01** Forward, no need-by: onsite row at `sampling`, entry 2026-10-08 → expected 2026-10-15, days_remaining 3, RAG green.
- **F03-AC-02** Backward, ample budget: onsite, offsite=false, stage `sampling`, entry 2026-10-01, need-by 2027-01-31 → remaining stages sampling(7), qc_testing(42), qa_release(7), B=56, A=122 → no compression. Must-complete-by: qa 2027-01-31, qc 2027-01-24, sampling 2026-12-13 → expected 2026-12-13.
- **F03-AC-03** Compression: stage `qc_testing`, entry 2026-10-01, need-by 2026-11-05 → B=49 (42+7), A=35, ratio=0.714… → compressed qc=30, qa=5 → expected = 2026-11-05 − 5 = 2026-10-31, compressed=true.
- **F03-AC-04** A ≤ 0: need-by 2026-09-30, entry 2026-10-01, stage `qa_release` → late, RAG red, expected 2026-09-30.
- **F03-AC-05** Re-eval: lot_type `09`, stage `qc_testing`, no need-by, entry 2026-10-01 → SLA 27 → expected 2026-10-28.
- **F03-AC-06** Applicability: 3PL + offsite row includes call_off and qc_ship. Onsite + onsite-test excludes both.
- **F03-AC-07** Adjusted date replaces the locked system date even when later than it (push-out).
- **F03-AC-08** Adjusted earlier than locked with reason `CAMPAIGN_PULLED_FORWARD`, and late → `late_reason_auto='CAMPAIGN_PULLED_FORWARD'`.
- **F03-AC-09** RAG boundaries: days_remaining −1 → red, 0 → amber, 2 → amber, 3 → green.
- **F03-AC-10** Exceptions sort: late rows (most overdue first) < ud_rejected < on_hold < air_gap < rest by expected (NULL last).
- **F03-AC-11** Period: overdue row is in the "this week" window; a row with expected next month is not; terminal rows are never in a period.
- **F03-AC-12** Air gap: approved 25 h ago, no UD → (true, 25). Approved 23 h ago → false. UD effective → false. UD rejected (`R`) → false. Approved 25 h ago, no UD, `erp_results_recorded_at` set → false (hours still 25).
- **F03-AC-13** An invalid profile (duplicate stage key) raises `ProfileError` naming the key.
- **F03-AC-14** `FixedClock` drives `now()`/`today()`. `HttpClock` falls back to `DbClock` when the scenario service is down (mocked).

> If any worked number above disagrees with the formulas in `03-domain-model` §5, **stop and raise an open question**. Do not change either silently.
