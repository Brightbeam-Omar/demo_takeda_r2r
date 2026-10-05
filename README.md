# R2R Intelligence Demo

A working, client-agnostic demonstration of a pharma Receipt-to-Release (R2R) batch-tracking and
orchestration solution. It shows the whole system end to end: sources, data product, sync,
application, human input and audit, AI agents, governance. All data is synthetic.

The specs in [`specs/`](specs/) are the source of truth. Start with [`CLAUDE.md`](CLAUDE.md) and
[`specs/06-roadmap.md`](specs/06-roadmap.md).

## Prerequisites

- Docker Desktop (Compose v2 and buildx)
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 for you)
- Node 20 or newer
- An Apple Silicon laptop with 16 GB available to Docker (Docker Desktop > Resources > Memory)

## Quickstart

```bash
cp .env.example .env   # local dev defaults; edit if you need to
make install           # uv sync + npm ci
make up                # builds and starts Postgres, the simulators, the pipeline and the app sync layer
make check             # lint, types, tests, leak scan (leak scan arrives with F02)
```

Check the databases with `docker compose exec postgres psql -U r2r -d postgres -l`: you should see
`erp_sim`, `lims_sim`, `qms_sim`, `app` and `dagster`.

## Services

| Service | Port | What it is |
|---|---|---|
| `postgres` | 5432 | One server, five databases |
| `scenario` | 8100 | Owns the demo clock: `GET /clock`, `POST /clock/set`, `POST /clock/advance` |
| `erp-sim` | 8101 | SAP-shaped ERP simulator |
| `lims-sim` | 8102 | LIMS simulator |
| `qms-sim` | 8103 | QMS simulator |
| `dagster-web` / `dagster-daemon` | 3001 | The data product pipeline (UI at http://localhost:3001) |
| `app-api` | 8000 | Application API: signed webhook `POST /api/sync/webhook`, `GET /api/sync/status`, admin `POST /api/sync/trigger` (F08) |
| `app-worker` | n/a | Drain worker: mirrors the published contract into the `app` database every `DRAIN_INTERVAL_SECONDS`. The only reader of the lakehouse, which it mounts read-only (F08) |

Every service serves OpenAPI docs at `/docs`. Reads are open; every `POST` needs the header
`X-Scenario-Token` (`SCENARIO_TOKEN` in `.env`). A one-shot `db-migrate` container migrates the `app`
database; each simulator migrates its own database when it starts.

## Commands

Run `make help` for the short list. Targets marked "not yet implemented" print the feature that
delivers them.

| Command | What it does |
|---|---|
| `make up` / `make down` | Start / stop the stack |
| `make logs` | Follow stack logs |
| `make check` | ruff, mypy `--strict`, pytest, frontend lint/typecheck/test, leak scan |
| `make fmt` / `make test` | Format Python / run all unit tests |
| `make integration` | Tests that need Postgres (starts the compose Postgres) |
| `make stack-test` | Acceptance tests against an isolated copy of the stack (own project and ports, torn down afterwards); the demo stack is untouched |
| `make coverage-core` | 100% branch-coverage gate on `r2r_core.sla` and `r2r_core.airgap` (part of `make check`) |
| `uv run python -m app_api.openapi`, then `npm run gen:api` in `frontend/` | Re-export the API schema (`services/app_api/openapi.json`, a test keeps it current) and regenerate the TypeScript client types (F09) |
| `make demo-reset` | Wipe state and rebuild the canonical opening state (F13) |
| `make seed` | Regenerate the `site_a` source data with the profile seed (wipes the three source DBs) from the host against the running stack, then run `make pipeline` |
| `make pipeline` | Trigger one pipeline run (F07); the worker mirrors it into the app within about 30 s (F08) |
| `make scenario STEP=<id>` | Apply a scripted scenario step (F13) |
| `make e2e` / `make e2e-headed` | Playwright run-of-show (F14) |
| `make record-agents` / `make record-video` | Record LLM replays / backup video (F12, F14) |
| `make doctor` | Environment checks (F14) |

Integration tests (they need a running Postgres) are skipped by `make check`:

```bash
uv run pytest tests/integration -m integration
```

## Leak scanner

`make check` runs `leakscan`. Locally, copy `.leakscan/denylist.example.txt` to `.leakscan/denylist.txt`
(gitignored) and fill in the real client terms. In CI the list is the GitHub secret `LEAKSCAN_DENYLIST`
(the content, not a path); without it CI fails. Details in [`tools/leakscan/README.md`](tools/leakscan/README.md).

## Rules worth knowing

- No client-identifying content, ever. The leak scanner (F02) enforces it.
- All "now" comes from the demo clock (`r2r_core.clock`), never the wall clock. `make check` fails on
  `datetime.now()`, `datetime.utcnow()`, `date.today()` or `time.time()` in any `src/`.
