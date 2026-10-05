# F16 · Plan
- `components/filters/{FilterBar,FilterPanel,PillRow,CampaignPills,FilterChips,PresetsMenu}.tsx`; `components/banners/{AdjustedBanner,InsightsBanner}.tsx`; `windows/{AdjustedNeedsByWindow,InsightsWindow}.tsx` on a shared `Modal` (Radix Dialog) and a minimal `DataTable`.
- Backend: `routers/{bookmarks,presets}.py`, overview `adjusted` and `insights` endpoints, migration.
- URL state stays the single source of truth for filters (as in F10). Presets store and restore the query string.

## Deviations
- **`air_gap_threshold_hours` on `/api/reference`** (F16-FR-09, T7). The Insights window's explanatory line needs `<air_gap.threshold_hours>`, which no endpoint served. It is added to `ReferenceOut` rather than hard-coding 24 in the UI.
- **Tag chips stay (OQ-085).** F10's inline tag chips move out of `FiltersBand` into `components/filters/TagChips.tsx` and render under the filter bar, unchanged, until F17's tag row replaces them. They also appear as `Tag: HOLD ×` collapse chips, so Clear all and the chip row agree.
- **Bookmarks and presets API shape.** `GET /api/bookmarks` returns the user's row keys; `POST` is idempotent (201 both times) and 404s on a row that is not in the mirror; `DELETE` is idempotent (204). The overview response carries `bookmarks` (all of the user's keys, whatever the filters) so the stars and the greyed Bookmarked button need no extra call. `bookmarked` is resolved in the `overview_filters` dependency, so the export, explain and the two window endpoints honour it too.
- **Preset query format.** A preset stores the URL's query string (`type=…&class=…&period=this_week`), not the API's bracketed form, so applying it is a plain parse into the URL filter state. Presets, like bookmarks, are personal and not audited.
- **`DataTable`.** The shared minimal table (`components/common/DataTable.tsx`) is built on TanStack Table with search-all-columns, sort, pagination, rows per page, Reset Table and a client-side CSV export of the filtered rows. F18 extends it.
