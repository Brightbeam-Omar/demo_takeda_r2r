# F20 · Plan
- Pipeline: `sql/reports/{pipeline_daily.sql, releases_weekly.sql}`. Extend the metrics window to 52.
- r2r_core: `reports.py`, pure and fully tested.
- app_api: `routers/reports.py`; mirror tables.
- UI: `pages/Reports.tsx` with `tabs/*`; Recharts components in `components/charts/*`.

## Deviations
- **Monthly metrics are computed from the snapshot, not from `metric_rows`.** The weekly contributing rows only cover the 52-week window, and the 12-month window is a little longer, so `30_monthly_metrics.sql.j2` joins the snapshot to its own month list. It follows the same SLA rule (the row's own `applicable_sla_json` entry).
- **`sql/reports/` holds the two report SQL files** (`10_pipeline_daily`, `20_releases_weekly`) and `r2r_pipeline/reports.py` runs them, as `metrics.py` does for the metrics. `snapshot_aggregate` writes the calendar itself when a caller skipped `setup` (tests do; Dagster never does).
- **New objects are copied through `publish` in the contract order, ahead of `pipeline_status_v`** (04 section 2). The watermark count is 15.
- **`r2r_core.reports` also holds `release_rate`, `coverage`, `trend`, `adherence_by_week` and `stage_metric_map`**, beyond the three functions of F20-FR-03, so the API only loads rows and shapes JSON. The module is in the 100% branch-coverage gate (`make coverage-core`).
- **Datagen adds closed demand lines and the expedite requests in `report_facts.py`**, after everything else is planned, on the new streams `f20_adherence` and `f20_expedites`. A test builds the plan without them and shows every batch, lot and earlier demand line is equal.
- **Release Rate does not chart the current week to date**, which is a partial week and would plunge to 0 on a Monday morning. The year of an ISO week is the year of its Thursday.
- **Trend cells are shaded green or red** (F20 layout): green at or above the green threshold, red below it. The amber band of the metric cards is not used here.
- **Late Items uses the shared F18 `DataTable`** (search, header filters, column chooser, export); the tab's Export button downloads the server CSV.
- **The Recharts range scrubber is `Brush`.** Colours are literal hex values (`lib/chartColours.ts`) because SVG fills do not resolve `var()` reliably.
