# F05 · Plan
- `services/datagen/src/datagen/{cli.py, world.py, timeline.py, quirks.py, stories.py, legacy_workbook.py, report.py}`.
- **World**: build materials, suppliers, locations and campaigns from the seeded `random.Random(seed)` (never the global random).
- **Timeline**: for each batch, sample arrival week, route (3PL vs onsite), offsite flag and stage durations. Then simulate day by day from demo-start−26 weeks, setting the clock with `FixedClock` and calling the F04 event functions in date order, so every `updated_at` is realistic.
- **Stories**: applied after the main timeline with explicit dates relative to `demo.start_datetime`.
- **Workbook**: openpyxl, styles and merged cells. Inject disagreements with a separate seeded RNG.
- Keep the distribution parameters in `datagen/params.yaml`, so the SME can tune them without code changes.

## Deviations
