# F13 · Plan
- `services/sources/scenario/src/scenario/{steps.py, runner.py, reset.py, api.py}`. The runner executes actions sequentially and yields progress events. Pipeline triggering uses the Dagster GraphQL `launchRun`, and completion is detected by polling the run status.
- Reset runs datagen in-process (import `datagen`) to avoid docker-in-docker. The scenario container does **not** mount the lakehouse. It wipes it via the Dagster `r2r_reset_lakehouse` job.
- The frontend Demo Controls panel uses `EventSource` for SSE.

## Deviations

- **Datagen runs as a child process, not by `import datagen`.** The generator fixes the process-wide demo clock for every event; inside the scenario service that would change the clock the service answers requests with. The scenario image gets the generator and the three simulator packages through a new `EXTRA_PATHS` build argument in `docker/python.Dockerfile`. Still no docker-in-docker, and still no lakehouse mount.
- **The reset holds a Postgres advisory lock** (`r2r_core.sync_lock`, OQ-148) from before the table clear until the pipeline has published. The drain worker takes it shared for each pass and skips the pass while the reset holds it (`app_api.sync.lock`), so a mirror pass can never copy the old lakehouse into the freshly cleared tables. The lock is released before the app is waited on.
- **The reset writes no audit row of its own**, because it clears `audit_event`. Step runs are audited (F13-FR-07), including refused ones (`outcome=precondition_failed`).
- **Step lookups:** identifiers the generator picks (sample, lot, deviation numbers) are looked up when a step runs (`vars` in the YAML). Preconditions read the application API, so a check matches the screen (OQ-150). `wait_sync` matches the Dagster run id, which is the pipeline `run_id` every watermark carries (OQ-151, checked on the live stack).
- **Browser access (OQ-147):** `/api/demo/*` in app-api (404 unless `DEMO_MODE`, 403 unless admin) forwards to the scenario service with the token.
- **Extra precondition kind** `adjusted_need_by` (for `pull-forward-B2077`) and an `X-Actor-User` header on the run endpoints (the audit actor).
