# F21 · Plan
- Pipeline: `row_hash()` macro shim; runs view assembled in `publish`; failures included from the run log.
- app_api: migration (attempts, drain_pass_id, heartbeat); worker loop updates; worker wakes every 2 s to check for pending events (reuse the existing `/api/sync/trigger` for Drain Queue Now); run-pipeline proxy; `routers/{runs,webhooks,teams,schema}.py`.
- tools: `contract_schema.py` parses the 04 tables into `contract.json`; a CI step diffs them.
- UI: `pages/admin/{SyncStatus,WebhookStatus,TeamDashboard,SchemaReference,SlaConfig,Placeholder}.tsx`.

## Deviations
- **`run_seq` in `pipeline_runs_v` (T2).** The demo clock does not tick, so two runs on the same demo day have the same `started_at` and the page could not tell which is newer. `pipeline_runs_v` therefore carries `run_seq` (wall-clock microseconds of the run's setup step, written by `run_step` into the log's `detail_json` as `wall_us`). Recorded in 04 §4.2d.
- **Where the comparison lives (T2).** `snapshot_aggregate` computes `row_hash` and counts `inserted` against `intelligence.row_hash_last`, but `publish` rewrites `row_hash_last` after the last object is written, so a run that fails after the snapshot step never moves the baseline (OQ-129). The hash itself is computed with the `row_hash()` macro in DuckDB over the snapshot table.
- **Latest run in its own history (T2).** `publish` builds `pipeline_runs_v` before `notify` exists, so the latest run's steps stop at a synthetic `publish` row and its duration excludes publish's tail and notify; the next publication shows the full run.
