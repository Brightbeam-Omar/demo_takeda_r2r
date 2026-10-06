# 02 · Architecture

## 1. Context

```
 SOURCE SIMULATORS (Postgres DBs + FastAPI)          DATA PRODUCT (Dagster + DuckDB + Delta)
 ┌───────────┐ ┌───────────┐ ┌───────────┐          ┌──────────────────────────────────────────┐
 │ erp_sim   │ │ lims_sim  │ │ qms_sim   │──extract─▶ setup → extract → transform →             │
 │ (SAP-     │ │ samples,  │ │ deviations│          │ snapshot_aggregate → publish → notify    │
 │  shaped)  │ │ approvals │ │ CAPA      │          │ lakehouse/{staging,intelligence,published}│
 └─────▲─────┘ └─────▲─────┘ └─────▲─────┘          └───────────────┬──────────────────────────┘
       │ scripted events            │                               │ POST /api/sync/webhook (HMAC)
 ┌─────┴────────────────────────────┴─┐                             ▼
 │ scenario engine + DEMO CLOCK       │          APPLICATION (FastAPI + Postgres `app` + React)
 └────────────────────────────────────┘          ┌──────────────────────────────────────────────┐
                                                 │ webhook receiver → sync_event (queue table)    │
                                                 │ drain worker (every 20 s) → ContractReader     │
                                                 │   → mirror_* upsert → watermark                │
                                                 │ REST API: reads mirror ⊕ overrides             │
                                                 │ React UI: Overview, Batch, Sync, Audit, Agents │
                                                 └──────────────┬───────────────────────────────┘
                                                                │ read-only tools
                                                 ┌──────────────▼───────────────────────────────┐
                                                 │ AGENT HARNESS: gateway · tools · validator    │
                                                 │ proposal · action_log · agent_trace           │
                                                 └──────────────────────────────────────────────┘
```

## 2. Services (docker-compose)

| Service | Image/base | Port (host) | Purpose |
|---|---|---|---|
| `postgres` | postgres:16 | 5432 | DBs: `erp_sim`, `lims_sim`, `qms_sim`, `app`, `dagster` |
| `erp-sim` | python:3.12-slim | 8101 | Admin/scenario API over `erp_sim` DB (sources are read by the pipeline over SQL) |
| `lims-sim` | python:3.12-slim | 8102 | REST API over `lims_sim` DB |
| `qms-sim` | python:3.12-slim | 8103 | REST API over `qms_sim` DB |
| `scenario` | python:3.12-slim | 8100 | Demo clock + scenario steps + reset orchestration |
| `dagster-web` | python:3.12-slim | 3001 | Dagster UI |
| `dagster-daemon` | same | n/a | Schedules (every 4 demo-hours, paused by default) and run queue |
| `app-api` | python:3.12-slim | 8000 | FastAPI: webhook, REST API |
| `app-worker` | same as app-api | n/a | Drain worker loop (and safety poll in Tier 2) |
| `agents` | python:3.12-slim | 8200 | Harness API: run agent, list proposals, approve/reject |
| `frontend` | node:20 → nginx | 5173 (dev) / 8080 | React app; proxies `/api` to app-api, `/agents-api` to agents |

The `./lakehouse` volume is mounted read-write into Dagster containers and **read-only** into `app-worker`. Nothing else mounts it. Demo reset wipes the lakehouse by launching the Dagster job `r2r_reset_lakehouse`.

## 3. Key flows

### 3.1 Pipeline run
1. Trigger: `make pipeline`, the Dagster UI, the scenario engine, or the schedule.
2. `setup`: load site profile, create a `run_id`, record `started_at` (demo clock).
3. `extract`: read source tables (SQL over Postgres) into `staging.*` Delta tables, overwritten each run. Record per-source `extracted_at` and the source's max `updated_at` (freshness).
4. `transform`: SQL builds the flattened batch rows and applies the **stage engine** (rules generated from the profile) and SLA columns.
5. `snapshot_aggregate`: write `intelligence.batch_snapshot` for `snapshot_date = demo today` (replace that partition predicate only) and compute `intelligence.weekly_metrics`.
6. `publish`: overwrite `published.*_v` Delta tables from the latest snapshot plus reference data from the profile.
7. `notify`: on success, POST signed webhook `{run_id, published_at}`.

### 3.2 Sync
1. `POST /api/sync/webhook` verifies `X-Signature: sha256=<hex>` (HMAC-SHA256 of the raw body with `WEBHOOK_SECRET`). On success it inserts `sync_event(status='pending', source='webhook')` and returns 202 in < 100 ms. It never reads the lakehouse.
2. `app-worker` loop every `DRAIN_INTERVAL_SECONDS` (default 20): claims rows with `SELECT … FOR UPDATE SKIP LOCKED` where `status='pending'`, or where `status='claimed' AND claimed_at < now - 5 min`.
3. For each claimed event, it reads every published object through `ContractReader`, upserts the `mirror_*` tables in **one transaction**, sets `watermark.run_id`, and marks the event `done` (or `failed` with the error).

### 3.3 Read
Every UI read hits app-api, which queries `mirror_*` LEFT JOIN current overrides. Responses include `contract_run_id` and `last_success_at` so the UI can show freshness.

### 3.4 Agent
`POST /agents-api/agents/air_gap/run` → agent reads via tools (app API, read-only) → model call via `ModelGateway` → output parsed into a `Proposal` → `Validator` runs deterministic checks → status `pending_approval` or `rejected_by_validator` → a human with the required role approves in the UI → action executor writes `action_log` (Tier 1: "ticket created" record plus rendered email in the UI; no real email sent). Every step goes to `agent_trace`.

## 4. Core interfaces (in `packages/r2r_core`)

```python
# clock.py
def now() -> datetime: ...            # reads demo clock from scenario service / shared table; tz-aware UTC
def today() -> date: ...

# profile.py
class SiteProfile(BaseModel): ...     # see 03-domain-model §2; load_profile(path|name) -> SiteProfile

# contract.py
class ContractReader(Protocol):
    def read(self, object_name: str) -> list[dict[str, Any]]: ...
    def status(self) -> PipelineStatus: ...
# PipelineStatus: frozen dataclass(last_run_id: str, started_at: datetime, last_success_at: datetime,
#                  row_count: int, source_freshness: dict[str, Any])
# Rows are plain Python values (date, tz-aware datetime, Decimal, bool, str, None); *_json columns stay strings.
# A missing object or an empty pipeline_status_v raises ContractUnavailable ("no published data yet").
# Tier 1 impl: DeltaContractReader(lakehouse_path). Tier 2 stub: DatabricksContractReader (Statement Execution API)

# sla.py: pure functions; see 03-domain-model §5
```

```python
# services/agents: gateway.py
class ModelGateway(Protocol):
    def complete(self, *, system: str, messages: list[Msg], tools: list[ToolSpec] | None,
                 response_schema: type[BaseModel] | None, trace_id: str) -> ModelResult: ...
# Providers: AnthropicGateway (env ANTHROPIC_API_KEY, MODEL_ID), BedrockGateway (Tier 2),
# ReplayGateway (looks up recorded responses by hash of (agent, input fingerprint); fails loudly on miss)
```

## 5. Demo clock
- Stored in `app` DB table `demo_clock(id=1, now_utc timestamptz, frozen bool)` and served by `scenario` at `GET /clock` and `POST /clock/advance {hours|days}`.
- The canonical opening time is set in the profile (`demo.start_datetime`, e.g. Monday 08:00 local).
- **The clock never ticks with wall time.** It moves only through `set`/`advance` (scenario steps, reset). This keeps screens, replay keys and checksums deterministic. `frozen` is reserved for future use.
- Every service uses `r2r_core.clock.now()`, which calls the scenario service with a 1 s cache, falling back to direct DB read. Pipeline runs record demo time, not wall time.

## 6. Configuration (`.env.example`)
`POSTGRES_*`, `WEBHOOK_SECRET`, `WEBHOOK_URL`, `DRAIN_INTERVAL_SECONDS=20`, `LAKEHOUSE_PATH=/lakehouse`, `SITE_PROFILE=site_a`, `CLOCK_SOURCE=http|db|fixed`, `SCENARIO_URL=http://scenario:8100`, `SCENARIO_TOKEN`, `DAGSTER_GRAPHQL_URL=http://dagster-web:3001/graphql`, `AGENTS_AUTORUN=false`, `LLM_PRICE_IN_PER_1K`, `LLM_PRICE_OUT_PER_1K`, `LEAKSCAN_DENYLIST` (CI only), `LLM_PROVIDER=replay|anthropic|bedrock`, `ANTHROPIC_API_KEY`, `MODEL_ID` (default `claude-sonnet-5-5`), `AWS_REGION` (Tier 2), `DEMO_MODE=true` (enables persona switcher and demo controls).

## 7. Identity in Tier 1
There is no SSO. In `DEMO_MODE`, the UI persona switcher sends `X-Demo-User: <user_key>`. app-api resolves the user and role from the `app_user` table and enforces permissions **server-side** on every write. The design keeps an `AuthProvider` interface so an OIDC/auth proxy can replace the header in Tier 2 (AWS).

## 8. Observability (Tier 1 minimum)
- Structured JSON logs with `service`, `run_id`, `event_id`, `trace_id`.
- Sync Status page (`/admin/sync`): every pipeline run (`pipeline_runs_v`) with per-step detail. Webhook Sync Status page (`/admin/webhooks`): queue health cards (pending, error, abandoned, safety-poll fallbacks, last drain from the worker heartbeat) and the last 50 `sync_event` rows. The worker wakes every 2 s and runs a full pass every `DRAIN_INTERVAL_SECONDS`.
- Dagster UI for pipeline runs.

## 9. Architecture decisions (record new ones in `specs/adr/`)
| ADR | Decision |
|---|---|
| ADR-001 | Postgres table as queue (`SKIP LOCKED`), not a broker: durable, at-least-once, no extra infra |
| ADR-002 | DuckDB + delta-rs locally with Spark-compatible SQL. A PySpark runner arrives in Tier 2 |
| ADR-003 | FastAPI over Django: faster to build and typed. The read/override/audit patterns are framework-agnostic |
| ADR-004 | Row grain = material + batch + inspection lot (single storage location per batch in synthetic data). Multi-location fan-out deferred |
| ADR-005 | Header-based demo identity behind an `AuthProvider` interface |
| ADR-006 | Agents are proposal-only, with a deterministic validator and human approval |
