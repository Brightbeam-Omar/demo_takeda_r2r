# F07 · Pipeline II: Snapshot, Metrics, Publish, Notify (Dagster)

## Functional requirements
| ID | Requirement |
|---|---|
| F07-FR-01 | `snapshot_aggregate`: write `intelligence.batch_snapshot` for `snapshot_date` (replace only that date's rows, idempotent). Update `intelligence.need_by_history` (insert first-seen `system_need_by_date` per `row_key`; never update existing) and derive `system_need_by_locked` (the first non-null value per row; see 04 §2.1) |
| F07-FR-02 | Weekly metrics per `03-domain-model` §7 for metrics with `computed_in: pipeline` → `intelligence.weekly_metrics` (last 12 complete ISO weeks plus current week-to-date, empty weeks included with NULL `pct`; see 03 §7 and 04 §2.1) and the contributing rows → `weekly_metric_rows_v` |
| F07-FR-03 | `publish`: overwrite all `published.*_v` objects in `04-data-contracts` §4 from the latest snapshot and profile. Add `run_id`, `published_at`. `pipeline_status_v` has exactly one row; it is written last |
| F07-FR-04 | `notify`: on success, POST `{"run_id":…, "published_at":…}` to `WEBHOOK_URL` with header `X-Signature: sha256=<hmac>`. The body is compact JSON (`separators=(",", ":")`) and is sent as the exact bytes that are signed; `published_at` is ISO 8601 UTC from the demo clock. Retry network errors and 5xx responses 3× after 1 s, 2 s and 4 s (delays are injectable so tests do not sleep); 4xx is not retried. `notify_status` is `ok`, `failed` or `skipped` (no `WEBHOOK_URL`). Any webhook outcome **does not** fail the run; it is logged and recorded in `pipeline_run_log.notify_status` |
| F07-FR-05 | `setup` step: create run context and record `started_at`. Every step writes a row to `intelligence.pipeline_run_log` (`run_id, step, status, started_at, finished_at, rows, error, notify_status, detail_json`). Ops pass only `run_id` and `snapshot_date` to each other; step details such as the source freshness go in `detail_json` |
| F07-FR-06 | Dagster: job `r2r_pipeline`, with ops `setup → extract → transform → snapshot_aggregate → publish → notify`. Schedule every 4 hours is **defined but stopped** (the demo clock does not tick; runs are triggered explicitly). Also a utility job `r2r_reset_lakehouse` (removes every table directory under `staging`, `intelligence` and `published`, and keeps the three folders; used by F13 reset). The pipeline job is runnable from the UI, `make pipeline` and the scenario service: `POST :8100/pipeline/run` (token-guarded with `X-Scenario-Token`) launches the job through the Dagster GraphQL API (`DAGSTER_GRAPHQL_URL`) and returns the Dagster run id; with `?wait=true` it polls until the run finishes and returns its status. `make pipeline` calls it with `wait=true` and exits non-zero when the run fails. The Dagster services use the demo clock (`CLOCK_SOURCE`), and the schedule uses Dagster's own cron and is stopped by default |
| F07-FR-07 | Failed run: no publish occurs, the previous published state remains intact, and `pipeline_run_log` shows the failed step |
| F07-FR-08 | A full run on the seeded dataset completes in < 60 s on the target laptop |

## Acceptance criteria
- **F07-AC-01** After `make pipeline`, all 8 published objects exist, and `pipeline_status_v` has 1 row with the new run_id.
- **F07-AC-02** Running twice on the same demo day yields identical `batch_snapshot` row counts for that date (idempotent).
- **F07-AC-03** `system_need_by_locked` stays at the first-seen value after demand moves later in a subsequent run.
- **F07-AC-04** A hand-built fixture with 10 sampling completions in a week, 8 within SLA, gives M3 pct = 80.0, and `weekly_metric_rows_v` has exactly those 10 rows for that week.
- **F07-AC-05** `metric_reference_v` shows M1, M2, M4, M5 as `awaiting_signal` with a non-empty `null_reason`.
- **F07-AC-06** The webhook receives a correctly signed body (verified by a test HTTP server using the same secret).
- **F07-AC-07** Forcing an exception in `transform` leaves `published.*` unchanged and logs the failure.
- **F07-AC-08** The run appears in the Dagster UI with all six ops green.
