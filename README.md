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
- A machine with 32 GB RAM (a 32 GB Apple Silicon laptop is the target)

## Quickstart

```bash
cp .env.example .env   # local dev defaults; edit if you need to
make install           # uv sync + npm ci
make up                # starts Postgres (the only service in F01)
make check             # lint, types, tests, leak scan (leak scan arrives with F02)
```

Check the databases with `docker compose exec postgres psql -U r2r -d postgres -l`: you should see
`erp_sim`, `lims_sim`, `qms_sim`, `app` and `dagster`.

## Commands

Run `make help` for the short list. Targets marked "not yet implemented" print the feature that
delivers them.

| Command | What it does |
|---|---|
| `make up` / `make down` | Start / stop the stack |
| `make logs` | Follow stack logs |
| `make check` | ruff, mypy `--strict`, pytest, frontend lint/typecheck/test, leak scan |
| `make fmt` / `make test` | Format Python / run all unit tests |
| `make coverage-core` | 100% branch-coverage gate on `r2r_core.sla` and `r2r_core.airgap` (part of `make check`) |
| `make demo-reset` | Wipe state and rebuild the canonical opening state (F13) |
| `make pipeline` | Trigger one pipeline run (F07) |
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
