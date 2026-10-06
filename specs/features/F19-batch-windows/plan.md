# F19 · Plan
- Sources: erp_sim migration (`zinbchk_item`, `resolved`); qms_sim migration (fields, severity, change control). Extend the event functions. Datagen generators for items and CCs.
- Pipeline: extract + `inbound_checks_v`, `change_controls_v`, `samples_v`. Stage engine `resolved` handling with rule tests. Re-run the seeded oracle.
- App: migrations (`status_log` + data migration, reason-code migration), mirror tables, routers, deprecations.
- UI: refactor `components/drawer/*` into the non-modal drawer (history sections plus summary sections with Open ↗ links; OQ-116). New `windows/{Inbound,Quality,StatusLog,SampleData,AdjustNeedsBy}Window.tsx`. Wire the F18 cells.
- Check W6 dates: with 6/37/6 backward from 26 Nov: QA 26 Nov, QCL Testing 26 Nov − 6 = 20 Nov, Sampling 20 Nov − 37 = 14 Oct ✓.

## Deviations
