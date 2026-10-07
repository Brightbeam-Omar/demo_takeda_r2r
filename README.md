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

Six commands from a clean clone to a demo you can present:

```bash
cp .env.example .env                                              # local defaults (offline: LLM_PROVIDER=replay)
cp .leakscan/denylist.example.txt .leakscan/denylist.txt          # then add the client terms (see "Leak scanner")
make install                                                      # uv sync + npm ci + the Playwright browser
make up                                                           # builds and starts everything (first build: several minutes)
make demo-reset                                                   # the opening state, in under 3 minutes
make doctor EXPECT_UP=1                                           # every line must say ok
```

**Present from http://localhost:8080** (the built app). The Vite dev server on http://localhost:5173 is for
development only. The presenter script is [`docs/demo-script.md`](docs/demo-script.md); the architecture on one page
is [`docs/architecture-overview.md`](docs/architecture-overview.md).

Check the databases with `docker compose exec postgres psql -U r2r -d postgres -l`: you should see
`erp_sim`, `lims_sim`, `qms_sim`, `app` and `dagster`.

## Presenter checklist

**The night before**
- [ ] `make doctor` (before `make up` it checks Docker, memory, ports, `.env` and the denylist), then `make up` and `make doctor EXPECT_UP=1`.
- [ ] `make e2e` passes (it resets the demo twice; allow about 10 minutes).
- [ ] `make record-video` if the backup video is missing or old: `artifacts/video/run-of-show.webm`.
- [ ] Read [`docs/demo-script.md`](docs/demo-script.md) once, with the SME.

**30 minutes before**
- [ ] Docker Desktop has 12 GB or more (Settings > Resources > Memory).
- [ ] `make demo-reset`, then `make doctor EXPECT_UP=1`: *recordings* and *replay keys: 4 of 4* must be `ok`.
- [ ] Browser on http://localhost:8080, 100% zoom, 1440×900, signed in as Pat. Do not click around.
- [ ] The legacy workbook `artifacts/legacy_tracker.xlsx` open in its own window.
- [ ] A terminal open here, for the recovery commands (`make scenario STEP=list`).

## Offline

The demo needs no internet once the images are pulled. `LLM_PROVIDER=replay` (the default) answers the agent from
the recordings in `services/agents/recordings/`, and the run-of-show test refuses and counts any request the browser
makes beyond this machine (it must be none). Only `make record-agents` and `LLM_PROVIDER=anthropic` need a network and
an `ANTHROPIC_API_KEY`.

## Troubleshooting

Start with `make doctor EXPECT_UP=1`: it prints the fix for what it finds.

| # | Symptom | Fix |
|---|---|---|
| 1 | "No recording for key …" when running the air-gap agent | The agents container has a stale recordings folder: `docker compose up -d --force-recreate agents` (`make demo-reset` does this by itself) |
| 2 | The agent says there is nothing to propose, or the Insights band shows other batches | The state is not the opening state: `make demo-reset` |
| 3 | A Demo Controls step is greyed out | Its precondition is not met (hover for why), usually because it already ran: `make demo-reset` to run it again |
| 4 | After a step the batch does not move | Run `make scenario STEP=run-pipeline`, wait 20 to 30 seconds. See the Webhook Sync Status page |
| 5 | `make up` fails with "port is already allocated" | Something else holds the port: `make doctor` names it. Stop it or change the `*_HOST_PORT` in `.env` |
| 6 | Containers restart or are killed | Docker has too little memory: set 12 GB or more in Docker Desktop, then `make up` |
| 7 | `make demo-reset` says `Missing .env` | `cp .env.example .env` |
| 8 | `make check` fails the leak scan with "no denylist" | `cp .leakscan/denylist.example.txt .leakscan/denylist.txt` and add the terms |
| 9 | `make e2e` fails on the first spec | The stack is not up or not healthy: `make doctor EXPECT_UP=1`. The failure screenshot and trace are in `artifacts/e2e-results/` |
| 10 | The page shows old numbers | The top bar says when the last sync was. `make pipeline`, wait for it, reload |

## Services

| Service | Port | What it is |
|---|---|---|
| `postgres` | 5432 | One server, five databases |
| `scenario` | 8100 | Owns the demo clock: `GET /clock`, `POST /clock/set`, `POST /clock/advance` |
| `erp-sim` | 8101 | SAP-shaped ERP simulator |
| `lims-sim` | 8102 | LIMS simulator |
| `qms-sim` | 8103 | QMS simulator |
| `dagster-web` / `dagster-daemon` | 3001 | The data product pipeline (UI at http://localhost:3001) |
| `frontend-web` | 8080 | The built app behind nginx: **present from here** (F14). `frontend` (5173) is the Vite dev server |
| `app-api` | 8000 | Application API: signed webhook `POST /api/sync/webhook`, `GET /api/sync/status`, admin `POST /api/sync/trigger` (F08) |
| `agents` | 8200 | The agent harness (F12): runs the air-gap agent, validates its drafts, holds proposals for a person to approve (UI: `/agents`). Reads app-api and the three simulators over HTTP; writes only `proposal`, `action_log`, `agent_trace` and `audit_event`, as the Postgres role `agents_rw`. Its model answers come from recordings (`LLM_PROVIDER=replay`, the default) or the Anthropic API. See `services/agents/README.md` |
| `app-worker` | n/a | Drain worker: mirrors the published contract into the `app` database every `DRAIN_INTERVAL_SECONDS`. The only reader of the lakehouse, which it mounts read-only (F08) |

Every service serves OpenAPI docs at `/docs`. Reads are open; every `POST` needs the header
`X-Scenario-Token` (`SCENARIO_TOKEN` in `.env`). A one-shot `db-migrate` container migrates the `app`
database; each simulator migrates its own database when it starts.

## Commands

Run `make help` for the short list.

| Command | What it does |
|---|---|
| `make up` / `make down` | Start / stop the stack |
| `make logs` | Follow stack logs |
| `make check` | ruff, mypy `--strict`, pytest, frontend lint/typecheck/test, leak scan |
| `make fmt` / `make test` | Format Python / run all unit tests |
| `make integration` | Tests that need Postgres (starts the compose Postgres) |
| `make stack-test` | Acceptance tests against an isolated copy of the stack (own project and ports, torn down afterwards); the demo stack is untouched |
| `make coverage-core` | 100% branch-coverage gate on `r2r_core.sla` and `r2r_core.airgap` (part of `make check`) |
| `make contract-json` | Regenerate `specs/contract.json`, the published contract the Schema Reference page shows (F21); `make check` fails when it is stale |
| `uv run python -m app_api.openapi`, then `npm run gen:api` in `frontend/` | Re-export the API schema (`services/app_api/openapi.json`, a test keeps it current) and regenerate the TypeScript client types (F09) |
| `make demo-reset` | Back to the demo-start state in under three minutes: clears bookmarks, overrides, status logs, proposals and the audit log, resets the clock, regenerates the source data with the profile seed, runs the pipeline and waits for the sync (F13). Same as the **Reset demo** button on Demo Controls |
| `make seed` | Developer shortcut: regenerate the `site_a` source data (wipes the three source DBs) from the host, then run `make pipeline`. It does not clear the app tables: for a clean demo use `make demo-reset` |
| `make pipeline` | Trigger one pipeline run (F07); the worker mirrors it into the app within about 30 s (F08) |
| `make scenario STEP=<id>` | Run a scripted scenario step through the real source systems, the pipeline and the sync, printing each progress line (F13); exits non-zero when the step is refused or fails. `make scenario STEP=list` shows the steps and whether each one can run now |
| `make e2e` / `make e2e-headed` | `make demo-reset`, then the run-of-show (acts 2, 3, 5 and 6, under 6 minutes), a second reset, then every other Playwright spec. HTML reports in `artifacts/e2e/` (F14) |
| `make record-agents` | Run the air-gap agent live for the four demo-start air gaps and record the model's answers into `services/agents/recordings/` (F12). Needs the stack in the demo-start state and `ANTHROPIC_API_KEY` with credit; the key is never printed |
| `make record-video` | Demo reset, then the run-of-show at presenter pace (`PACE=presenter`: 4 to 6 s on each key screen, a visible pointer, slow clicks, captions; about 7 to 8 minutes), 1440×900, with no voice-over: `artifacts/video/run-of-show.webm` (and `.mp4` when `ffmpeg` is installed) (F14) |
| `make doctor` | Environment checks, each failure with its fix: Docker, memory ≥ 12 GB, ports, `.env`, the denylist, the Dagster and app health, the agents' recordings mount and the replay keys for the 4 demo-start air gaps. `make doctor EXPECT_UP=1` also fails when the stack is not running (F14) |

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
