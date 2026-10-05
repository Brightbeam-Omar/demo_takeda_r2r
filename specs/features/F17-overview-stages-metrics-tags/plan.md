# F17 · Plan
- erp_sim: migration `0003_ekpo`, events in `events.py`, GR closes the line. datagen: `timeline.py` creates PO lines before arrivals.
- pipeline: `extract` adds `ekpo`; `transform/46_expected_deliveries.sql` (portable SQL); publish order puts the new object before `pipeline_status_v`.
- app: mirror table + reader registration; overview multi-stage; expected-deliveries router.
- UI: `components/pipeline/{StageStrip,StageCard,ExpectedDeliveryCard,OnHoldCard}.tsx`, `components/metrics/MetricCard.tsx`, `components/tags/TagRow.tsx`, `windows/ExpectedDeliveriesWindow.tsx`.
- ISO week label: use `date-fns` `getISOWeek` in the site timezone.

## Deviations
