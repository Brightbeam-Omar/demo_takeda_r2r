# F08 · Plan
- `services/app_api/src/app_api/{main.py, db/models.py, db/migrations/, sync/webhook.py, sync/drain.py, sync/mirror.py, sync/status.py}`, with the worker entrypoint `python -m app_api.worker`.
- Mirror replace: inside one transaction, `TRUNCATE mirror_x; COPY/INSERT …` for each object (sizes are small). Set `mirrored_at` and `contract_run_id`.
- `app-worker` uses the same image as `app-api`, with a different command.
- Integration tests are marked `@pytest.mark.integration` and use the compose Postgres or testcontainers.

## Deviations
- Flat layout (OQ-055): keep F04's `app_api/{models.py, db.py, migrate.py, migrations/}` instead of `db/models.py` and `db/migrations/`; add `app_api/sync/`. One migration `0002_app_schema` creates every §5 table and seeds the five users.
- Mirror replace uses `DELETE` + insert, not `TRUNCATE` (OQ-052): no exclusive lock, readers keep the old mirror until commit.
- `deltalake` and `pyarrow` are in the app image (the worker needs them); F08-AC-07 guards the webhook module's import graph.
