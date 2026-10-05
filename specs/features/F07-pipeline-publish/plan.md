# F07 · Plan
- `services/pipeline/src/r2r_pipeline/{snapshot.py, metrics.py, publish.py, notify.py, dagster_defs.py}` with SQL in `sql/metrics/*.sql` (same portability rules).
- Delta partition replace: use `deltalake.write_deltalake(..., mode="overwrite", predicate="snapshot_date = '…'")`.
- Overwrite each published object directly in the order of 04 §4. With Delta, overwrite is atomic per table. Publish `pipeline_status_v` **last**, so its run_id implies the others are complete.
- Dagster deployment: `dagster.yaml` with Postgres storage (`dagster` DB), and `workspace.yaml` pointing to `r2r_pipeline.dagster_defs`.
- HMAC: `hmac.new(secret, raw_body, sha256).hexdigest()` over the exact bytes sent.

## Deviations
- Publish writes each object straight to its final name; the plan's temp-table-and-swap step is dropped because Delta has no rename-swap and a per-table overwrite is already atomic (OQ-047). A crash inside `publish` can leave a mix of runs; every object carries `run_id` and `pipeline_status_v` is last, and F08 checks for the mixed state.
- Weekly metrics SQL gets its week list and the per-row SLAs as two small input tables registered by Python (`metric_weeks`, `row_sla`), so the SQL stays inside the portable function allow-list (no date truncation, no JSON functions).
- Schema evolution (added after F09 added two published columns): `write_delta` appends and `replace_partition` pass `schema_mode="merge"` (deltalake 1.6.6 accepts it with `mode="append"` and with a partition `predicate` overwrite), so new columns are NULL for older dates; full overwrites (staging, published, wholesale `intelligence` tables) already used `schema_mode="overwrite"`. A new column in a contract therefore needs no lakehouse reset (`test_schema_evolution.py`).
