# F01 · Plan

- **Python:** root `pyproject.toml` with `[tool.uv.workspace] members = ["packages/*", "services/datagen", "services/pipeline", "services/app_api", "services/agents", "services/sources/*", "tools/leakscan"]` (add members as their features create them). Each member has `src/<pkg>/` and `tests/`. Shared dev deps: ruff, mypy, pytest, pytest-cov.
- **Ruff config:** line length 110, rules `E,F,I,B,UP,SIM,RUF`. Formatter on.
- **Clock guard:** `tools/checks/test_no_wallclock.py`, a pytest test that walks `**/src/**/*.py` with `ast` and flags `Call` nodes for `datetime.now`, `datetime.utcnow`, `date.today` and `time.time` (allow-list: `r2r_core/clock.py`). Run as part of `pytest`.
- **Postgres init:** `docker/postgres/init/01-create-dbs.sql`.
- **Frontend:** `npm create vite@latest frontend -- --template react-ts`, add Tailwind, ESLint (typescript-eslint, react-hooks) and Vitest + Testing Library. Scripts: `dev`, `build`, `lint`, `typecheck`, `test`.
- **Makefile:** use `docker compose` (v2). `check` chains the steps and stops on first failure.
- **CI:** `astral-sh/setup-uv`, `actions/setup-node@v4`, run `make check` (it skips docker-dependent tests by marker `@pytest.mark.integration`, which runs in a later job with `services: postgres`).

## Deviations
- **Frontend versions (T6):** the Vite `react-ts` template now ships React 19, TypeScript 6 and oxlint. Pinned instead to the spec: React 18.3, TypeScript 5.9, ESLint 9 (typescript-eslint, react-hooks), Vite 7. Tailwind is v4 via `@tailwindcss/vite`. Vitest uses jsdom and Testing Library.
- **Workspace members (T2):** explicit list, `packages/r2r_core` only for now (OQ-002). `tools/checks` is a plain pytest folder, not a member.
- **Dockerfile (T5):** installs with `uv pip install` of `packages/r2r_core` then `SERVICE_PATH`, instead of `uv sync --package`, so it works before any service exists (OQ-006).
- **CI (T8):** added a third job building the image for `linux/amd64` only (OQ-006). The integration job runs the init SQL with `psql` because service containers cannot mount the init directory.
- **Ruff excludes (T3):** `specs/` and `*.md` are excluded from `ruff format`, because ruff 0.16 reformats Markdown and F01-FR-11 requires specs to stay unchanged.
- **Extras:** `make install` and `make help`; `psycopg` added to the dev group for the AC-01 integration test, which reads `R2R_TEST_PG_HOST` (default `localhost`) because `postgres` only resolves inside compose.
- **Task ticks:** boxes were ticked together at T9 rather than per task.
