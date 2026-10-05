# F06 · Pipeline I: Extract, Flatten, Stage Engine

## Context
This is the heart of the data product: deterministic derivation of where every batch is, from source data. Portable SQL (constitution P6), run here by DuckDB over Delta.

## Functional requirements
| ID | Requirement |
|---|---|
| F06-FR-01 | `extract` step: copy every source table listed in `04-data-contracts` §2 into `staging.stg_*` Delta tables (overwrite), raw (`stg_mseg` keeps every movement). Record per-source `max(updated_at)` and `extracted_at` (demo clock) for freshness |
| F06-FR-02 | Extract filters (on `qals` only): `art IN ('01','09')`; drop lots with cancel UD codes. Netting of goods receipts happens in `transform` (`04-data-contracts` §3: a `102` cancels at most one `101` of the same batch, posting date and quantity; the receipt is treated as never happened) |
| F06-FR-03 | `transform` step builds `staging.batch_flat` per `04-data-contracts` §3 with SQL files in `services/pipeline/sql/transform/*.sql`, executed in lexical order |
| F06-FR-04 | **Stage engine SQL generated from the profile**: `stage_engine.py` renders `sql/transform/50_stage.sql.j2` (Jinja) into a `CASE` in priority order from `03-domain-model` §4, emitting `stage_key`, `stage_rule_id`, the derived inputs `cycle_start_date` and `ud_effective`, `stage_sort` and stage entry/exit dates. UD codes and SLAs come from the profile, never literals |
| F06-FR-05 | Applicable SLA list per row → `applicable_sla_json` (ordered list of `{stage_key, sla_days}` honouring re-eval overrides and `applies_if`) |
| F06-FR-06 | `system_need_by_date`: earliest open `mdez.bdter ≥ snapshot_date` for the material. Joined to every non-released row of that material |
| F06-FR-10 | The stage engine output is the separate table `staging.batch_stage` (`04-data-contracts` §3b); `batch_flat` stays the engine's input |
| F06-FR-07 | Derivations per `04-data-contracts` §3 (including `erp_results_recorded_at` = `qals.zresrec`). Flags per `03-domain-model` §6 (except `expedite` and `air_gap`, which are app-side). Plus `deviation_light`, `inbound_light`, `open_deviation_count`, `closed_deviation_count`, `source_refs_json` |
| F06-FR-08 | **SQL portability**: transforms use only an allow-listed function set (`CASE, COALESCE, CAST, MIN, MAX, SUM, COUNT, ROW_NUMBER, LAG, LEAD`, comparison, `date_add_days()`, `date_diff_days()`, `site_date()` and `concat_key()` macros). A macro shim maps the macros to the right dialect, with a test per macro and dialect. `applicable_sla_json` and `source_refs_json` are built in Python from the staged tables, `applicable_sla_json` through `r2r_core.sla`. A unit test parses each SQL file with `sqlglot` for both `duckdb` and `spark` dialects and fails on unknown functions |
| F06-FR-09 | Steps are plain Python functions (`extract(ctx)`, `transform(ctx)`), independent of Dagster, so they are testable without it. F07 wraps them as Dagster ops |

## Acceptance criteria
- **F06-AC-01** On the seeded dataset, the stage engine agrees with `artifacts/expected_stages.csv` for ≥ 99% of rows, and 100% for story batches. Mismatches are listed in the test output.
- **F06-AC-02** A unit test per rule (`R-REL` … `R-PND`) with a minimal hand-built row proves the priority order (e.g. a row satisfying both `R-QAR` and `R-SMP` conditions → `qa_release`).
- **F06-AC-03** A rejected UD row → `qa_release` with `ud_rejected=true`. A cancelled-UD lot → absent.
- **F06-AC-04** A same-day 101+102 pair (and no later 101) → the row is `pending` (`gr_date` NULL).
- **F06-AC-05** A re-eval row has SLAs from `reeval_sla_overrides` in `applicable_sla_json`.
- **F06-AC-06** Changing a stage SLA in a copy of the profile changes `applicable_sla_json` with no code change.
- **F06-AC-07** The sqlglot portability test passes for every transform file in both dialects.
- **F06-AC-08** `source_refs_json` for `B1042` contains its `qals` lot, `mseg` docs and LIMS sample ID.
