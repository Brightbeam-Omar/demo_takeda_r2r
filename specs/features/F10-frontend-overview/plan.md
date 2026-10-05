# F10 · Plan
- `frontend/src/{app/, api/ (generated), components/{shell,filters,flow-strip,metrics,table,common}/, pages/Overview.tsx, state/url-filters.ts, lib/format.ts}`.
- Vite dev server proxies `/api` → app-api:8000 and `/agents-api` → agents:8200. In production, nginx does the same.
- Polling: React Query `refetchInterval: 10000` on overview and status. Diff rows by `row_key` + `stage_key` + `expected_completion` to drive highlights.
- Table: TanStack Table + TanStack Virtual.

## Deviations
- **Reference carries the site timezone.** The demo clock must show site-local time (`Mon 12 Oct 2026 08:00`, 05), but `/api/clock` returns UTC and `/api/reference` had no timezone. Added `site_timezone` (from the profile) to `ReferenceOut` in F09's reference router, with the OpenAPI export regenerated. Additive, no behaviour change.
- **Rows carry the current location.** The Overview table has a Location column (05) but `RowOut` had no location. Added `storage_location` and `location_type` (both already in the mirror) to F09's `RowOut`, with the OpenAPI export regenerated. Additive.
