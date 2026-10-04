# F06 · Plan
- `services/pipeline/src/r2r_pipeline/{context.py, lake.py, extract.py, transform.py, stage_engine.py, sql_shim.py}`, `services/pipeline/sql/transform/{10_stock.sql, 20_lots.sql, 30_lims.sql, 40_quality.sql, 45_demand.sql, 50_stage.sql.j2, 60_flags.sql, 90_batch_stage.sql}`.
- **Rules live in `packages/r2r_core/src/r2r_core/stage_rules.py`** as an ordered `RULES: list[StageRule(id, stage_key, condition_sql, description)]`. The Jinja template renders the CASE from this list. F09 reuses it for "Explain", so it is the single definition.
- `lake.py`: `read_delta(name) -> duckdb relation` (via `deltalake` → arrow → duckdb) and `write_delta(name, arrow_table, mode)`.
- Extract reads Postgres with `duckdb`'s postgres extension, or SQLAlchemy → arrow (choose the simpler of the two and record the choice in Deviations).
- `RunContext`: `run_id` (the **Dagster run id** when run under Dagster; a uuid4 in plain unit tests), `profile`, `snapshot_date` = demo today, `lake_root`, `freshness` dict.
- Golden tests use a tiny **hand-built fixture world** (about 20 rows) in addition to the seeded dataset test.

- Dependencies for this package only: `duckdb`, `deltalake`, `pyarrow`, `jinja2`, `sqlglot`, `sqlalchemy`, `psycopg`.

## Deviations
- **Extract reads Postgres with SQLAlchemy → arrow** (OQ-043), not DuckDB's Postgres extension: no extension download, works offline and on both architectures.
