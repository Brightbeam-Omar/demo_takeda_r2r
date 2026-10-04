# T2-09 · Lineage (OpenLineage/Marquez) & PySpark Portability

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Show governed lineage and prove the data product runs on Spark/Databricks unchanged.

## Scope
- Emit OpenLineage events from each pipeline step (datasets in/out, column lineage for published objects); Marquez + web UI in compose (optional profile `lineage`)
- 'Explain' links to the Marquez dataset view
- PySpark runner (local mode, optional compose profile) executing the same SQL files; portability test compares outputs DuckDB vs Spark on the seeded dataset (row-level equality)
- `databricks.yml` bundle and `DatabricksContractReader` implemented (Statement Execution API) but untested without a workspace; documented port guide

## Acceptance sketch
- Spark and DuckDB published outputs identical on seeded data
- Marquez shows source → staging → intelligence → published graph
