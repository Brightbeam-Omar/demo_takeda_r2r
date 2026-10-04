# services/pipeline

The data product's first half (F06): `extract(ctx)` copies the source tables into Delta staging tables and
`transform(ctx)` builds `staging.batch_flat` (the input of the stage engine) and `staging.batch_stage` (its
output). Transforms are SQL files in `sql/transform/`, run in lexical order on DuckDB and kept to the
Spark-SQL-compatible subset (constitution P6). The steps are plain Python functions; F07 wraps them in Dagster.
