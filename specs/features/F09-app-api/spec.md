# F09 · Application API: Reads, Overrides, Audit, RBAC, Explain

## Context
The REST API behind the UI. It composes the mirror with current overrides and applies `r2r_core.sla` at read time.

## Endpoints
| Method & path | Role | Description |
|---|---|---|
| `GET /api/me` | any | Current user and role (from `X-Demo-User`, default `pat` in DEMO_MODE) |
| `GET /api/clock` | any | Proxy of scenario `/clock` (demo now, today, frozen) |
| `GET /api/users` | any (DEMO_MODE) | Personas for the switcher |
| `GET /api/reference` | any | Stages, metrics, reason codes, molecule types and classes (`{key, label}`), campaigns (distinct from mirror), profile site name, profile `terms`, `release_badge` (env `RELEASE_BADGE`), `air_gap_threshold_hours` (F16) |
| `GET /api/overview` | any | Query: `type[]`, `class[]`, `campaign[]`, `stage`, `flags[]`, `period` (`all`,`this_week`,`last_week`,`next_week`,`this_month`,`last_month`,`next_month`,`custom`), `from`, `to`, `q` (search material/batch), `bookmarked` (true = only the user's bookmarks; `class[]=unknown` matches a NULL class, OQ-086). Returns `{freshness, flow_strip:[{stage_key,count,breached}], on_hold_count, total, mode:'snapshot'|'due_in_period', alerts:[…], adjusted_count, bookmarks:[row_key…], rows:[…]}` |
| `GET /api/metrics` | any | Weekly metrics (12 weeks + current) and reference, honouring the same filters where computable (Tier 1: unfiltered, flag `filtered:false`) |
| `GET /api/rows/{row_key}` | any | Full row: facts, plan, overrides (current + history), comments, deviations, sibling lots of same batch (history) |
| `GET /api/rows/{row_key}/explain?field=stage|expected_completion` | any | Row explanation payload (see FR-06) |
| `GET /api/explain?field=metric:M3&week=…` or `field=flow:<stage_key>` (+ overview filters) | any | Metric / flow-count explanation (see FR-06) |
| `PUT /api/rows/{row_key}/need-by` | planner, admin | Body `{adjusted_date|null, reason_code, expedite:bool, note}`. Reason is required when setting a date. Returns the recomputed row |
| ~~`PUT /api/rows/{row_key}/status`~~ | removed in F21-FR-07 | superseded by the F19 status log (`POST /api/rows/{row_key}/status-log`) |
| ~~`POST /api/rows/{row_key}/comments`~~ | removed in F21-FR-07 | superseded by the F19 status log |
| `GET /api/audit` | any | Paginated audit events, filter by row_key/actor/action and a demo-date range (`from`, `to`, inclusive, site timezone; F11, OQ-068) |
| `GET /api/export.csv` | any | Current overview rows (filters applied; same in-flight default as the overview, F17-FR-10) |
| `GET /api/expected-deliveries` | any | Open PO lines (F17): `period` filters and `type[]`/`class[]`/`campaign[]`; stage, tags and bookmarks never apply |
| `GET /api/bookmarks` | any | The current user's bookmarked `row_key`s (F16) |
| `POST /api/bookmarks/{row_key}` · `DELETE /api/bookmarks/{row_key}` | any (incl. viewer) | Set / remove a personal bookmark. Idempotent. Not audited (OQ-091) |
| `GET /api/presets` · `POST /api/presets` | any (incl. viewer) | The user's saved filter presets · `{name, query}` → 201, or 409 when the user already has that name (F16, OQ-089) |
| `PUT /api/presets/{id}` · `DELETE /api/presets/{id}` | owner | Overwrite a preset's query (`{query}`, name unchanged) · delete it. Another user's id is 404 |
| `GET /api/overview` additions (F17) | any | `stage` repeats (OR); `include_released` (default false) — released rows appear only with `include_released=true`, a `released` stage or the `released` flag; `flags[]` also accepts `released` and `release_on_coa` (zero rows until F18); the response gains `batch_count` and `skip_count` per flow entry whose stage has `applies_if` |
| `GET /api/overview/adjusted` | any | Non-released rows with a current adjusted need-by, honouring every overview filter except `stage`; newest override first (F16-FR-07, OQ-090) |
| `GET /api/overview/insights` | any | Every air-gap row honouring every filter except `stage`, worst-first, with `days_gap` (F16-FR-09) |
| `POST /api/feedback` | any (incl. viewer) | `{page, message}` → stores a `feedback` row (F15). Not audited |
| `GET /api/feedback` | admin | Feedback, newest first (F15) |

## Functional requirements
| ID | Requirement |
|---|---|
| F09-FR-01 | Every row in responses includes: facts from mirror, `operative_need_by`, `adjusted_need_by_date`, `expedite`, `manual_status`, `plan` (`PlanResult` from F03), `air_gap`/`air_gap_hours`, `late`, `days_in_stage`, deviation/inbound lights, flags, `comment_count` |
| F09-FR-02 | Default `rows` order is exceptions-first (`r2r_core.sla.exception_sort_key`). Period filtering uses `r2r_core.sla.in_period`. Flow-strip counts reflect all filters **except** the stage filter. `breached` = any row in that stage is late |
| F09-FR-03 | `alerts`: air-gap rows (count + top 5), late count, on-hold count, rejected count |
| F09-FR-04 | Overrides: insert-only versioning per `04-data-contracts` §5 in one transaction with an `audit_event` holding `{field, old, new, reason_code, note}`. Clearing = a new version with null |
| F09-FR-05 | RBAC enforced server-side by a dependency `require_role(*roles)`. Forbidden → 403 + `audit_event(action='forbidden')`. Unknown `X-Demo-User` → 401. When not DEMO_MODE, the header is rejected (Tier 2 `AuthProvider`) |
| F09-FR-06 | Explain: for `stage` → matched `stage_rule_id`, the rule's condition text and description (from `r2r_core.stage_rules`), the values of the rule's `inputs` columns (published, including `cycle_start_date` and `ud_effective`), `source_refs_json`, `contract_run_id`, `last_success_at`. For `expected_completion` → plan inputs (entry date, operative need-by and whether adjusted, applicable/effective SLAs, compression ratio) and the formula in words. For `metric:Mx` → week, completed, on_time, SLA, and the contributing rows from `mirror_weekly_metric_rows` (never recomputed). For `flow:<stage_key>` → the count, the active filters, the mode (snapshot / due in period), the rule(s) that place rows in that stage, and the row_keys |
| F09-FR-07 | Responses carry `contract_run_id` and `freshness_minutes`. Overview p95 < 300 ms for ~800 rows |
| F09-FR-08 | OpenAPI schema is generated, and the frontend generates its TS client from it (`npm run gen:api`) |

## Decisions (OQ-056 to OQ-062)
- **Need-by PUT:** only changed fields (`adjusted_need_by_date`, `expedite`) get a new version, with one audit event per changed field, in one transaction. `reason_code` must exist in `mirror_reason_codes` (422) and is required when a date is set; clearing needs none. A no-op PUT writes nothing. Unknown row 404; released row 409; pending rows may be adjusted; any date is accepted.
- **Status PUT:** `value_json = {rag, team}`, `reason` is stored in `note` and is required when setting; `rag: null` clears. A manual status is display-only: it never changes the plan, `late`, ordering, `breached` or alerts.
- **Audit actions:** `need_by_set`, `need_by_cleared`, `expedite_set`, `expedite_cleared`, `status_set`, `status_cleared`, `comment_added`, `forbidden` (`row_key` from the path, `details_json = {method, path, required_roles, role}`). `GET /api/users` needs no identity and is 404 unless `DEMO_MODE=true`. `/api/clock` falls back to `demo_clock` when scenario is down. `GET /api/audit`: `limit` (50, max 200), `offset`, newest first, filters `row_key`, `actor`, `action`, and `from`/`to` (added in F11, OQ-068).
- **Overview:** values within a filter are ORed and filters are ANDed (`flags[]` is OR). Windows are Monday to Sunday and the calendar month in the site timezone from the demo clock; `custom` needs both `from` and `to` (422). No pagination: `total = len(rows)`. The flow strip has one entry per stage in reference order. `alerts` and `on_hold_count` honour all filters except `stage`; `rejected` counts `ud_rejected` or `lims_rejected` and returns both numbers.
- **Explain:** each `StageRule` has `inputs`, and Explain shows exactly those published columns. `week` is the ISO Monday date (default: current week). An `awaiting_signal` metric returns its `null_reason` and no rows. `flow:` has no row cap.
- **Cache:** key is run id, max override id, max comment id and demo-clock now to the second, 5 s TTL.
- **Export:** CSV has the system and the adjusted need-by date as separate columns; all roles may export. `row_key` is URL-encoded (`%7C`) in paths.
- **OpenAPI:** `openapi.json` is committed (exported by `python -m app_api.openapi`) and `frontend` gets `npm run gen:api` using `openapi-typescript`.

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
