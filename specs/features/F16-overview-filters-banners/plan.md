# F16 · Plan
- `components/filters/{FilterBar,FilterPanel,PillRow,CampaignPills,FilterChips,PresetsMenu}.tsx`; `components/banners/{AdjustedBanner,InsightsBanner}.tsx`; `windows/{AdjustedNeedsByWindow,InsightsWindow}.tsx` on a shared `Modal` (Radix Dialog) and a minimal `DataTable`.
- Backend: `routers/{bookmarks,presets}.py`, overview `adjusted` and `insights` endpoints, migration.
- URL state stays the single source of truth for filters (as in F10). Presets store and restore the query string.

## Deviations
