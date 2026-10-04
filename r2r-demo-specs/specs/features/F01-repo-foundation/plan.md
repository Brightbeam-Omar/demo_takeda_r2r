# F01 · Plan

- **Python:** root `pyproject.toml` with `[tool.uv.workspace] members = ["packages/*", "services/datagen", "services/pipeline", "services/app_api", "services/agents", "services/sources/*", "tools/leakscan"]` (add members as their features create them). Each member has `src/<pkg>/` and `tests/`. Shared dev deps: ruff, mypy, pytest, pytest-cov.
- **Ruff config:** line length 110, rules `E,F,I,B,UP,SIM,RUF`. Formatter on.
- **Clock guard:** `tools/checks/test_no_wallclock.py`, a pytest test that walks `**/src/**/*.py` with `ast` and flags `Call` nodes for `datetime.now`, `datetime.utcnow`, `date.today` and `time.time` (allow-list: `r2r_core/clock.py`). Run as part of `pytest`.
- **Postgres init:** `docker/postgres/init/01-create-dbs.sql`.
- **Frontend:** `npm create vite@latest frontend -- --template react-ts`, add Tailwind, ESLint (typescript-eslint, react-hooks) and Vitest + Testing Library. Scripts: `dev`, `build`, `lint`, `typecheck`, `test`.
- **Makefile:** use `docker compose` (v2). `check` chains the steps and stops on first failure.
- **CI:** `astral-sh/setup-uv`, `actions/setup-node@v4`, run `make check` (it skips docker-dependent tests by marker `@pytest.mark.integration`, which runs in a later job with `services: postgres`).

## Deviations
_(record here)_
