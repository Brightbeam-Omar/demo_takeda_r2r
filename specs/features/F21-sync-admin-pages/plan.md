# F21 · Plan
- Pipeline: `row_hash()` macro shim; runs view assembled in `publish`; failures included from the run log.
- app_api: migration (attempts, drain_pass_id, heartbeat); worker loop updates; worker wakes every 2 s to check for pending events (reuse the existing `/api/sync/trigger` for Drain Queue Now); run-pipeline proxy; `routers/{runs,webhooks,teams,schema}.py`.
- tools: `contract_schema.py` parses the 04 tables into `contract.json`; a CI step diffs them.
- UI: `pages/admin/{SyncStatus,WebhookStatus,TeamDashboard,SchemaReference,SlaConfig,Placeholder}.tsx`.

## Deviations
