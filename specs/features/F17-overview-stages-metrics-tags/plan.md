# F17 · Plan
- erp_sim: migration `0003_ekpo`, events in `events.py`, GR closes the line. datagen: `timeline.py` creates PO lines before arrivals.
- pipeline: `extract` adds `ekpo`; `transform/46_expected_deliveries.sql` (portable SQL); publish order puts the new object before `pipeline_status_v`.
- app: mirror table + reader registration; overview multi-stage; expected-deliveries router.
- UI: `components/pipeline/{StageStrip,StageCard,ExpectedDeliveryCard,OnHoldCard}.tsx`, `components/metrics/MetricCard.tsx`, `components/tags/TagRow.tsx`, `windows/ExpectedDeliveriesWindow.tsx`.
- ISO week label: use `date-fns` `getISOWeek` in the site timezone.

## Deviations
- **ISO week label:** `date-fns` is not a dependency of the frontend and one small pure function is enough, so `lib/calendar.ts` gets `isoWeek(iso)` (ISO week and week-year of the published `week_start`, unit-tested at the year boundaries). No timezone conversion is needed because `week_start` is already a site-local date.
- **SQL file name:** the expected-deliveries step is `transform/46_expected_deliveries.sql`, not `95_`: it reads `t_need` from `45_demand.sql`, and the stage-engine tests run only the files from `50` upwards on a hand-built `batch_flat`, which has no `stg_ekpo`.
- **Datagen:** PO lines are planned by `datagen/po_lines.py` at the end of `build_plan` (tunable numbers in `params.yaml` under `po_lines`) rather than inside `timeline.py`, so the existing planning code and its streams are untouched.
- **Frontend folders:** the strip lives in `components/pipeline/` and the tag row in `components/tags/`; `components/flow-strip/` (F10) is deleted, since the alert band and the old strip are both replaced.
