# F09 · Application API: Reads, Overrides, Audit, RBAC, Explain

## Context
The REST API behind the UI. It composes the mirror with current overrides and applies `r2r_core.sla` at read time.

## Endpoints
| Method & path | Role | Description |
|---|---|---|
| `GET /api/me` | any | Current user and role (from `X-Demo-User`, default `pat` in DEMO_MODE) |
| `GET /api/clock` | any | Proxy of scenario `/clock` (demo now, today, frozen) |
| `GET /api/users` | any (DEMO_MODE) | Personas for the switcher |
| `GET /api/reference` | any | Stages, metrics, reason codes, molecule types, classes, campaigns (distinct from mirror), profile site name |
| `GET /api/overview` | any | Query: `type[]`, `class[]`, `campaign[]`, `stage`, `flags[]`, `period` (`all`,`this_week`,`last_week`,`next_week`,`this_month`,`custom`), `from`, `to`, `q` (search material/batch). Returns `{freshness, flow_strip:[{stage_key,count,breached}], on_hold_count, total, mode:'snapshot'|'due_in_period', alerts:[…], rows:[…]}` |
| `GET /api/metrics` | any | Weekly metrics (12 weeks + current) and reference, honouring the same filters where computable (Tier 1: unfiltered, flag `filtered:false`) |
| `GET /api/rows/{row_key}` | any | Full row: facts, plan, overrides (current + history), comments, deviations, sibling lots of same batch (history) |
| `GET /api/rows/{row_key}/explain?field=stage|expected_completion` | any | Row explanation payload (see FR-06) |
| `GET /api/explain?field=metric:M3&week=…` or `field=flow:<stage_key>` (+ overview filters) | any | Metric / flow-count explanation (see FR-06) |
| `PUT /api/rows/{row_key}/need-by` | planner, admin | Body `{adjusted_date|null, reason_code, expedite:bool, note}`. Reason is required when setting a date. Returns the recomputed row |
| `PUT /api/rows/{row_key}/status` | qc_lead, qa_release, admin | `{rag:'red'|'amber'|'green', reason, team}` |
| `POST /api/rows/{row_key}/comments` | all except viewer | `{body}` |
| `GET /api/audit` | any | Paginated audit events, filter by row_key/actor/action |
| `GET /api/export.csv` | any | Current overview rows (filters applied) |

## Functional requirements
| ID | Requirement |
|---|---|
| F09-FR-01 | Every row in responses includes: facts from mirror, `operative_need_by`, `adjusted_need_by_date`, `expedite`, `manual_status`, `plan` (`PlanResult` from F03), `air_gap`/`air_gap_hours`, `late`, `days_in_stage`, deviation/inbound lights, flags, `comment_count` |
| F09-FR-02 | Default `rows` order is exceptions-first (`r2r_core.sla.exception_sort_key`). Period filtering uses `r2r_core.sla.in_period`. Flow-strip counts reflect all filters **except** the stage filter. `breached` = any row in that stage is late |
| F09-FR-03 | `alerts`: air-gap rows (count + top 5), late count, on-hold count, rejected count |
| F09-FR-04 | Overrides: insert-only versioning per `04-data-contracts` §5 in one transaction with an `audit_event` holding `{field, old, new, reason_code, note}`. Clearing = a new version with null |
| F09-FR-05 | RBAC enforced server-side by a dependency `require_role(*roles)`. Forbidden → 403 + `audit_event(action='forbidden')`. Unknown `X-Demo-User` → 401. When not DEMO_MODE, the header is rejected (Tier 2 `AuthProvider`) |
| F09-FR-06 | Explain: for `stage` → matched `stage_rule_id`, the rule's condition text and description (from `r2r_core.stage_rules`), the field values used, `source_refs_json`, `contract_run_id`, `last_success_at`. For `expected_completion` → plan inputs (entry date, operative need-by and whether adjusted, applicable/effective SLAs, compression ratio) and the formula in words. For `metric:Mx` → week, completed, on_time, SLA, and the contributing rows from `mirror_weekly_metric_rows` (never recomputed). For `flow:<stage_key>` → the count, the active filters, the mode (snapshot / due in period), the rule(s) that place rows in that stage, and the row_keys |
| F09-FR-07 | Responses carry `contract_run_id` and `freshness_minutes`. Overview p95 < 300 ms for ~800 rows |
| F09-FR-08 | OpenAPI schema is generated, and the frontend generates its TS client from it (`npm run gen:api`) |

## Acceptance criteria
- **F09-AC-01** As `sam` (viewer), `PUT /need-by` → 403 and an audit row `forbidden`.
- **F09-AC-02** At demo start (2026-10-12), as `pat`, setting B2077 need-by from 2026-12-03 to **2026-11-26** with `CAMPAIGN_PULLED_FORWARD` returns `plan.compressed=true`, effective SLAs sampling 6 / qc_testing 37 / qa_release 6, expected completion **2026-10-14**, RAG **amber** (was 2026-10-15, green), and a new override version 1. Setting again → version 2, and v1 `is_current=false`.
- **F09-AC-03** Clearing the override restores `operative_need_by = system_need_by_locked`, and history keeps all versions.
- **F09-AC-04** Overview default order puts the late, rejected, on-hold and air-gap rows in that order before others (fixture).
- **F09-AC-05** `period=this_week` includes overdue rows and excludes released rows. `mode='due_in_period'`.
- **F09-AC-06** Explain `stage` for B1042 returns rule `R-QCT` with its field values and source refs.
- **F09-AC-07** Explain `metric:M3` lists contributing rows whose count equals `completed`.
- **F09-AC-08** B5003 appears in `alerts` air-gap with `air_gap_hours ≥ 30` at demo start.
- **F09-AC-09** The overview performance test (800 rows) p95 < 300 ms.
- **F09-AC-10** Export CSV row count equals overview total with the same filters.
