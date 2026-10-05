# F18 · Plan
- `components/datatable/{DataTable,Toolbar,Pagination,ColumnsPanel,HeaderFilter}.tsx` (shared); `components/overview/cells/*`; `components/overview/RowActionsMenu.tsx`.
- r2r_core: extend `plan()` with `coa_release`; add `profile.ReleaseOnCoa`. Tests first.
- app_api: hold/coa endpoints in the overrides service (same versioning + audit path as need-by); export router; compose `on_hold` display.
- erp_sim/datagen/pipeline: `qnext` column end to end (small migration and transform column).
- Search highlight: a single `highlight(text, q)` helper used by every cell renderer.

## Deviations
