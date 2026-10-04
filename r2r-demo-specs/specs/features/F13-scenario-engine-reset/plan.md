# F13 · Plan
- `services/sources/scenario/src/scenario/{steps.py, runner.py, reset.py, api.py}`. The runner executes actions sequentially and yields progress events. Pipeline triggering uses the Dagster GraphQL `launchRun`, and completion is detected by polling the run status.
- Reset runs datagen in-process (import `datagen`) to avoid docker-in-docker. The scenario container does **not** mount the lakehouse. It wipes it via the Dagster `r2r_reset_lakehouse` job.
- The frontend Demo Controls panel uses `EventSource` for SSE.

## Deviations
