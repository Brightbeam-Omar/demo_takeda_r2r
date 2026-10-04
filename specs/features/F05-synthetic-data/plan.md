# F05 · Plan
- `services/datagen/src/datagen/{cli.py, world.py, timeline.py, quirks.py, stories.py, legacy_workbook.py, report.py}`.
- **World**: build materials, suppliers, locations and campaigns from the seeded `random.Random(seed)` (never the global random).
- **Timeline**: for each batch, sample arrival week, route (3PL vs onsite), offsite flag and stage durations. Then simulate day by day from demo-start−26 weeks, setting the clock with `FixedClock` and calling the F04 event functions in date order, so every `updated_at` is realistic.
- **Stories**: applied after the main timeline with explicit dates relative to `demo.start_datetime`.
- **Workbook**: openpyxl, styles and merged cells. Inject disagreements with a separate seeded RNG.
- Keep the distribution parameters in `datagen/params.yaml`, so the SME can tune them without code changes.

## Deviations
- **Planning is separate from replay.** `planner.py` builds a pure, seeded `Plan`; `events.py` turns it into dated event-function calls and `executor.py` replays them. The distribution, quirk and story checks are therefore fast unit tests on the plan, and only the replay needs Postgres.
- **Target-driven timeline.** Instead of simulating arrivals and hoping the mix comes out right, each lot's current state is decided first (stage and age, or usage decision date) and the earlier stages are built backward from it. The stage mix, 3PL and offsite shares are then exact by construction, and per-week on-time targets use error diffusion so weekly M3/M6/M7 percentages land in the band.
- **Master data without an event function.** F04 has no event for materials, suppliers or storage locations, so the executor writes them once with the models directly, before the first event (FR-01 covers transactional data).
- **New F04 event.** F04 has no way to write `test_result` rows and FR-01 forbids raw inserts, so `lims_sim.events.test_result_recorded` (and `POST /events/test-result`) was added, with tests, for the seeded story-batch results (OQ-033).
- **Campaigns** are listed in `world.py` (the site profile has no campaigns key).
- **Re-eval lots on onsite batches only.** A re-evaluation lot of a batch first received at a 3PL would have a call-off exit earlier than its entry, so re-eval batches are received onsite.
- **Volumes.** 650 batches, 800 lots (150 of them re-eval, which is 120 x 1.25, inside the allowed uplift of up to 40%). The report states the actual counts.
- **Determinism check without `pg_dump`.** The AC-01 test reads every table of the three databases in a stable order and compares the two runs (the only column excluded is the serial `test_result.id`). This is the same comparison as a normalised data-only dump, with no dependency on a `pg_dump` binary on the host.
