# CLAUDE.md: R2R Intelligence Demo

You are building **R2R Intelligence Demo**, a working, client-agnostic demonstration of a pharma Receipt-to-Release (R2R) batch-tracking and orchestration solution. It is used in sales conversations. It must show the *whole system* working end to end (sources → data product → sync → application → human input/audit → AI agents → governance), not just a UI.

The work is **spec-driven**. The specs in `specs/` are the source of truth. Do not invent requirements.

## Read order (every session)

1. `specs/00-constitution.md`: non-negotiable principles. Never violate these.
2. `specs/06-roadmap.md`: feature order, dependencies and status.
3. `specs/02-architecture.md`, `specs/03-domain-model.md` and `specs/04-data-contracts.md`: the shared model every feature relies on. For any UI work, also read `specs/05-ux-guidelines.md`.
4. The `spec.md`, `plan.md` and `tasks.md` of the feature you are working on.

## How to work a feature

1. Pick the **lowest-numbered feature in `specs/06-roadmap.md` whose status is `ready`** and whose dependencies are all `done`. If the human names a feature, do that one.
2. Read its `spec.md` completely. If anything is ambiguous or conflicts with another spec, **stop and add an entry to `specs/OPEN_QUESTIONS.md`**, then ask the human. Do not guess on domain logic.
3. Follow `plan.md`. If you need to deviate (better library, simpler structure), record the deviation and the reason in the feature's `plan.md` under `## Deviations` before you implement it.
4. Implement `tasks.md` in order. Work test-first where the task says **[TDD]**. Tick each checkbox (`- [x]`) as you complete it.
5. After each task, run `make check` (lint, type check, tests, leak scan). Do not move on with a red build.
6. Commit once per task with Conventional Commits, referencing IDs, e.g. `feat(F06): stage engine priority rules [F06-FR-04]`.
7. When every task is done and every acceptance criterion in `spec.md` passes, set the feature to `review` in `specs/06-roadmap.md` and **stop for human review**. Do not start the next feature unprompted.

## Tech stack (Tier 1, local-first)

| Concern | Choice |
|---|---|
| Language | Python 3.12 (backend/data/agents), TypeScript 5 (frontend) |
| Python tooling | `uv`, `ruff` (lint+format), `mypy --strict` on `src/`, `pytest` |
| Containers | Docker + docker-compose (Compose v2). Everything runs with `make up` |
| Operational DBs | PostgreSQL 16 (one server, separate databases: `erp_sim`, `lims_sim`, `qms_sim`, `app`, `dagster`) |
| Lakehouse | Delta Lake via `deltalake` (delta-rs) on a local volume `./lakehouse` |
| Transforms | DuckDB executing SQL files kept to the **Spark-SQL-compatible subset** (see constitution P6) |
| Orchestration | Dagster (webserver + daemon) |
| API | FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 |
| Frontend | React 18 + Vite + TypeScript + Tailwind + TanStack Query + TanStack Table |
| LLM | `ModelGateway` abstraction. Providers: `anthropic` (default for local), `bedrock` (later on AWS), `replay` (offline/deterministic) |
| E2E tests | Playwright |

Target hardware: an Apple Silicon laptop with 16 GB available to Docker. All images must build for `linux/arm64` and `linux/amd64`.

## Repository layout

```
r2r-demo/
  CLAUDE.md
  Makefile
  docker-compose.yml
  .env.example
  config/site-profiles/        # site_a.yaml (default), site_b.yaml (Tier 2)
  docker/                      # python.Dockerfile, postgres/init/
  docs/                        # demo-script.md, architecture-overview.md, runbooks/
  artifacts/                   # generated (gitignored): legacy workbook, reports, e2e, video
  packages/
    r2r_core/                  # shared: site profile loader, demo clock, domain enums, SLA maths
  services/
    sources/erp_sim/           # SAP-shaped ERP simulator (Postgres + seed + FastAPI admin)
    sources/lims_sim/          # LIMS simulator (FastAPI)
    sources/qms_sim/           # QMS simulator (FastAPI)
    sources/scenario/          # scenario engine + demo clock API
    datagen/                   # seeded synthetic data generator
    pipeline/                  # Dagster code location + SQL transforms
    app_api/                   # FastAPI app: webhook, drain worker, API, overrides, RBAC
    agents/                    # harness: gateway, tools, validator, proposals, agents (+ recordings/ for replay)
  frontend/                    # React app
  tests/e2e/                   # Playwright demo-path tests
  tools/leakscan/              # client-term leak scanner
  tools/checks/                # repo guard tests (e.g. no wall-clock calls)
  specs/                       # these specs (copied in at F01)
```

## Commands (created in F01; keep them working)

- `make up` / `make down`: start/stop the full stack
- `make demo-reset`: wipe all state, regenerate seed data, run the pipeline once, sync. Must finish in < 3 min
- `make check`: ruff, mypy, pytest, frontend lint/typecheck/test, leak scan
- `make e2e`: demo reset, then Playwright run-of-show (`make e2e-headed` to watch)
- `make fmt`, `make test`, `make logs`
- `make record-agents`: record LLM replays (needs `ANTHROPIC_API_KEY`)
- `make doctor`: environment checks · `make record-video`: backup demo recording
- `make pipeline`: trigger one pipeline run now
- `make scenario STEP=<id>`: apply a scripted scenario step

## Hard rules

- **No client-identifying content, ever.** No real company, site, person, product, campaign, system brand or supplier names in code, data, comments, fixtures or commits. Use the generic vocabulary in `specs/03-domain-model.md` §9. `make check` runs the leak scanner. A leak fails the build.
- **Never read or copy files from outside this repository** (for example client folders on the machine). The specs are self-contained.
- **The application never writes to the lakehouse or source systems.** Agents write only to `proposal`, `action_log`, `agent_trace` and `audit_event`.
- **All "now" comes from the demo clock** (`r2r_core.clock.now()`), never `datetime.now()`. A lint rule enforces this (F01).
- Secrets come only from `.env` (gitignored). `.env.example` documents every variable.
- **Re-record after data or tool changes.** Any change to datagen, the published contract or the agent tools (anything the air-gap agent reads or the model sees) is followed, in the same PR, by `make demo-reset && make record-agents && make doctor EXPECT_UP=1`. The recordings are keyed on what the agent saw; CI fails when the replay keys of the 4 demo-start air gaps are missing after a reset.
- Prefer boring, readable code over cleverness. This is a demo that people will read on screen.
