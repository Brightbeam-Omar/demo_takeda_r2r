# F09 · Plan
- `services/app_api/src/app_api/{auth.py, deps.py, routers/{me,reference,overview,metrics,rows,audit,export}.py, services/{compose.py, overrides.py, explain.py}}`.
- `compose.py`: load mirror rows + current overrides (single query with LEFT JOIN LATERAL or two queries + dict merge), build `RowFacts`, call `r2r_core.sla.plan`, flags, air gap. Pure, so it is unit-testable with fixtures.
- Rule condition text: F06 renders the CASE from a `RULES` list in `r2r_core.stage_rules` (id, stage, condition_sql, description). F09 reads the same list for explanations. **If F06 put the rules elsewhere, refactor them into `r2r_core.stage_rules` here and record the change.**
- The mirror is small, so cache composed rows per `contract_run_id` + override max(id) for 5 s.

## Deviations
