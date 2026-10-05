# F09 · Plan
- `services/app_api/src/app_api/{auth.py, deps.py, routers/{me,reference,overview,metrics,rows,audit,export}.py, services/{compose.py, overrides.py, explain.py}}`.
- `compose.py`: load mirror rows + current overrides (single query with LEFT JOIN LATERAL or two queries + dict merge), build `RowFacts`, call `r2r_core.sla.plan`, flags, air gap. Pure, so it is unit-testable with fixtures.
- Rule condition text: F06 renders the CASE from a `RULES` list in `r2r_core.stage_rules` (id, stage, condition_sql, description). F09 reads the same list for explanations. **If F06 put the rules elsewhere, refactor them into `r2r_core.stage_rules` here and record the change.**
- The mirror is small, so cache composed rows per `contract_run_id` + override max(id) for 5 s.

## Deviations
- OQ-060: F09 touches F06/F07/F08 to publish `cycle_start_date` and `ud_effective` and to add `StageRule.inputs`, instead of recomputing them in Python. The mirror gets them through a new migration `0003_mirror_rule_inputs`.
- Cache key and its inputs follow OQ-061.
- Auth: a request without `X-Demo-User` is `pat` on every endpoint in DEMO_MODE (the spec states the default only for `/api/me`), so the UI need not send the header for the opening persona. F08's "no header on trigger is 401" test became 403.
