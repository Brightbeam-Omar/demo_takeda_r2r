# F18 · Plan
- `components/datatable/{DataTable,Toolbar,Pagination,ColumnsPanel,HeaderFilter}.tsx` (shared); `components/overview/cells/*`; `components/overview/RowActionsMenu.tsx`.
- r2r_core: extend `plan()` with `coa_release`; add `profile.ReleaseOnCoa`. Tests first.
- app_api: hold/coa endpoints in the overrides service (same versioning + audit path as need-by); export router; compose `on_hold` display.
- erp_sim/datagen/pipeline: `qnext` column end to end (small migration and transform column).
- Search highlight: a single `highlight(text, q)` helper used by every cell renderer.

## Deviations
- **Cell files.** The plan names `components/overview/cells/*`. The cells are in `components/overview/cells.tsx` and the column definitions in `columns.tsx`: one file each reads better than a folder of one-liners. The `Column<T>` type adds `text` (the displayed text) next to `cell`, so search, header filters, sorting and the CSV export all read what the cell shows.
- **Window tables are not migrated** (OQ-105). `components/common/DataTable.tsx` stays for the F16 and F17 windows: its tests expect Reset Table to clear the search and page sizes of 10/25/50, which F18-FR-01 changes. F19 moves the windows it touches onto `components/datatable`.
- **ARIA grid on the `<table>`.** The scroll box is a plain `div` and the `<table role="grid" tabindex="0">` takes the focus and the keys, because a `grid` wrapping a native `table` fails axe (`aria-required-children`). The star, the batch link, the pencil and the `⋯` button are out of the Tab order (`tabindex=-1`) so that one Tab reaches the table; the keyboard hint under the table names the keys.
- **Search runs in the browser.** `q` stays in the URL, but it is no longer sent to `/api/overview` (the search box moved from the filter bar into the table toolbar). The stage cards, the flow strip and the banners therefore do not move while typing.
- **Toggle overrides keep `on: false`.** Turning a hold or a COA release off stores `{"on": false, "reason": ...}` rather than a null, so the history keeps the reason for the release (04 §5 updated).
- **`released` in the row flags.** `FlagsOut.released` was added so the RELEASED tag chip needs no profile lookup in the browser.
- **Stage hues.** `--color-stage-N` moved into `@theme static` with hex values: Tailwind dropped them as unused, so every `var(--color-stage-N)` was unresolved (the stage badge needs them; the F17 card bars read them too).
