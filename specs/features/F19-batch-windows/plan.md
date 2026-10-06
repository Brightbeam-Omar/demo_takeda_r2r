# F19 · Plan
- Sources: erp_sim migration (`zinbchk_item`, `resolved`); qms_sim migration (fields, severity, change control). Extend the event functions. Datagen generators for items and CCs.
- Pipeline: extract + `inbound_checks_v`, `change_controls_v`, `samples_v`. Stage engine `resolved` handling with rule tests. Re-run the seeded oracle.
- App: migrations (`status_log` + data migration, reason-code migration), mirror tables, routers, deprecations.
- UI: refactor `components/drawer/*` into the non-modal drawer (history sections plus summary sections with Open ↗ links; OQ-116). New `windows/{Inbound,Quality,StatusLog,SampleData,AdjustNeedsBy}Window.tsx`. Wire the F18 cells.
- Check W6 dates: with 6/37/6 backward from 26 Nov: QA 26 Nov, QCL Testing 26 Nov − 6 = 20 Nov, Sampling 20 Nov − 37 = 14 Oct ✓.

## Deviations
- **Migrations keep the original author (OQ-111, OQ-112).** The status-log copy and the reason-code migration are written by Alembic with the *original* author on every new log row or override version, and one `audit_event` by `system` per change. A new row authored by `system` would need an `app_user` row (`override_value` and `status_log` point at `app_user`), and a `system` user would then show in the persona switcher. Nothing is updated or deleted: a superseded override version is only flagged `is_current = false`, as every new version does.
- **`sample_count` is read at read time from `mirror_samples`**, not published in `batch_pipeline_v` (04 §4.9). `latest_status` comes from `status_log` the same way, so the published contract of the batch row did not change.
- **The drawer takes its data from `GET /api/rows/{row_key}`**, which now also returns `inbound_check`, `changes` and `samples` next to the extended `deviations`, so the drawer's summary sections and the windows use one request and one query key. No separate window endpoints were added.
- **Drawer under a window (OQ-114, OQ-116).** A window opened from the drawer is `?win=<name>&row=<row_key>&drawer=open`; closing it leaves `?row=<row_key>` and the drawer showing. A window opened from a table cell has no `drawer=open`, so closing it removes both parameters. Opening a window for another row while the drawer is open swaps the drawer to that row when the window closes (the URL carries one row).
- **The drawer sits beside the table, not over it.** It is a flex column next to the Overview's `main` (560 px, `max-w-[45vw]`), so the table narrows instead of being covered and the top bar stays reachable. Escape closes it unless a dialog is open.
- **The Batch filter on close** is a controlled request (`filterRequest` on the shared `DataTable`), because the table keeps its header filters in its own state.
- **`DataTable` gains `compact`** (no second toolbar, no pager) for the Sample Data window. The Insights window is untouched (OQ-115).
- **F11's Plan section is folded into the Need-by summary** (system, adjusted, reason, set by, expected completion with its ⓘ, compression), because the new drawer section list has no Plan section and the Explain popover for expected completion has to stay.
- **Seeded checks outside `make check`:** the datagen integration run takes about 4 minutes (the generator replays 5,484 events per test that calls `generate`).
