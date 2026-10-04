# F08 · Plan
- `services/app_api/src/app_api/{main.py, db/models.py, db/migrations/, sync/webhook.py, sync/drain.py, sync/mirror.py, sync/status.py}`, with the worker entrypoint `python -m app_api.worker`.
- Mirror replace: inside one transaction, `TRUNCATE mirror_x; COPY/INSERT …` for each object (sizes are small). Set `mirrored_at` and `contract_run_id`.
- `app-worker` uses the same image as `app-api`, with a different command.
- Integration tests are marked `@pytest.mark.integration` and use the compose Postgres or testcontainers.

## Deviations
