# F07 · Plan
- `services/pipeline/src/r2r_pipeline/{snapshot.py, metrics.py, publish.py, notify.py, dagster_defs.py}` with SQL in `sql/metrics/*.sql` (same portability rules).
- Delta partition replace: use `deltalake.write_deltalake(..., mode="overwrite", predicate="snapshot_date = '…'")`.
- Publish to temp table names, then swap (write each object fully before any pointer update). With Delta, overwrite is atomic per table. Publish `pipeline_status_v` **last**, so its run_id implies the others are complete.
- Dagster deployment: `dagster.yaml` with Postgres storage (`dagster` DB), and `workspace.yaml` pointing to `r2r_pipeline.dagster_defs`.
- HMAC: `hmac.new(secret, raw_body, sha256).hexdigest()` over the exact bytes sent.

## Deviations
