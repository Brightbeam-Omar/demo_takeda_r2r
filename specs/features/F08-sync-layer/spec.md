# F08 · Sync Layer: Webhook, Queue, Drain, Mirror

## Context
This is the glue between data product and app, following constitution P2 and ADR-001. The demo shows it on screen, so its state must be inspectable.

## Functional requirements
| ID | Requirement |
|---|---|
| F08-FR-01 | `app-api` creates the app DB schema (Alembic) for every table in `04-data-contracts` §5 (extending F04's `0001_demo_clock` migration) and seeds `app_user` per `04-data-contracts` §5 (`pat`, `quinn`, `alex`, `sam`, `admin`) |
| F08-FR-02 | `POST /api/sync/webhook`: verify the HMAC over the raw body with constant-time compare. Invalid → 401 + `audit_event(action='webhook_rejected')`. Valid → insert `sync_event(source='webhook', status='pending', run_id)` and return **202** with the event id. Must not touch the lakehouse. p95 < 100 ms |
| F08-FR-03 | `POST /api/sync/trigger` (admin only) inserts `sync_event(source='manual')` |
| F08-FR-04 | `app-worker` drain loop every `DRAIN_INTERVAL_SECONDS`: claim with `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1` where `status='pending'`, or `status='claimed' AND claimed_at < now() − interval '5 minutes'` (stale reclaim) |
| F08-FR-05 | For a claimed event: read **every** published object through `ContractReader` (`DeltaContractReader`). If `pipeline_status_v.last_run_id == watermark.run_id` for all objects, mark `done` with `rows_upserted=0` (no-op). Otherwise replace all `mirror_*` tables **in one transaction**, update the `watermark` rows and mark `done` with counts. On exception, mark `failed` with the error text, and roll back the mirror |
| F08-FR-05b | Mixed-state check (OQ-047): the pipeline writes the published objects one by one with `pipeline_status_v` last. Before the transaction, the worker compares the `run_id` of every published object that carries one with `pipeline_status_v.last_run_id`. If they differ (a publish that crashed part-way, or one still in progress), the event is marked `failed` with a clear error and the mirror is untouched; the next webhook or manual trigger retries |
| F08-FR-06 | The worker is the **only** code path that reads the lakehouse. Its container mounts `./lakehouse` read-only |
| F08-FR-07 | `GET /api/sync/status`: last 50 events, watermark per object, `pipeline_status` (last_run_id, last_success_at, source_freshness), and computed `freshness_minutes = now − last_success_at` (demo clock) |
| F08-FR-08 | Structured logs for claim/pull/upsert, with `event_id`, `run_id` and duration |
| F08-FR-09 | `packages/r2r_core/contract.py` also defines `DatabricksContractReader` as a documented stub raising `NotImplementedError` (port path, Tier 2) |

## Acceptance criteria
- **F08-AC-01** After `make pipeline`, within `DRAIN_INTERVAL_SECONDS + 10 s`, `mirror_batch_pipeline` row count equals the published row count and the watermark equals the new run_id.
- **F08-AC-02** A bad signature → 401, no `sync_event` row, and one `audit_event`.
- **F08-AC-03** Two workers running concurrently never process the same event (integration test with two threads/processes and one pending row).
- **F08-AC-04** A worker killed after claiming (simulated by setting `claimed_at` 6 min ago with status `claimed`) is reclaimed and completed by the next drain.
- **F08-AC-05** A duplicate webhook for the same run_id → second event completes as a no-op (`rows_upserted=0`).
- **F08-AC-06** A failure mid-upsert (injected) leaves the previous mirror intact and marks the event `failed`.
- **F08-AC-08** Published objects whose `run_id` values disagree with `pipeline_status_v` leave the mirror unchanged and mark the event `failed` (F08-FR-05b).
- **F08-AC-07** The webhook endpoint never imports or calls the lakehouse reader (a test asserts module import graph / monkeypatch raises if called).
