# services/pipeline

The data product. Six steps, each a plain Python function that Dagster wraps in an op:

| Step | What it does | Feature |
|---|---|---|
| `setup` | creates the run context (`run_id`, snapshot date = the demo's today) and logs the start | F07 |
| `extract` | copies the source tables into `staging.stg_*` Delta tables | F06 |
| `transform` | SQL builds `staging.batch_flat` and, through the stage engine, `staging.batch_stage` | F06 |
| `snapshot_aggregate` | `intelligence.batch_snapshot` (one partition per day), `need_by_history`, weekly metrics | F07 |
| `publish` | overwrites the eight `published.*_v` objects, `pipeline_status_v` last | F07 |
| `notify` | POSTs the HMAC-signed `{run_id, published_at}` to `WEBHOOK_URL`; never fails the run | F07 |

Every step appends a row to `intelligence.pipeline_run_log`. A step that raises is logged as `failed` and stops
the run, so `publish` never runs and the previous published state stays.

SQL lives in `sql/transform/` and `sql/metrics/`, runs on DuckDB and is kept to the Spark-SQL-compatible subset
(constitution P6; `portability.py` checks it).

## Running it

```bash
make up          # Postgres, simulators, scenario, dagster-web (http://localhost:3001), dagster-daemon
make pipeline    # starts the Dagster job through the scenario service and waits; fails if the run fails
```

The 4-hourly schedule is defined but stopped (the demo clock does not tick). `r2r_reset_lakehouse` removes every
Delta table and keeps the `staging`, `intelligence` and `published` folders (F13 uses it for the demo reset).
