# F01 · Repo Foundation & Tooling

## Context
This feature lays the skeleton every later feature builds on: monorepo layout, Python workspace, frontend scaffold, docker-compose with Postgres, Makefile, quality gates and CI.

## User stories
- As a developer, I can clone the repo, copy `.env.example` to `.env`, run `make up`, and get a running (empty) stack.
- As a developer, I run `make check` and get one pass/fail verdict across Python and TypeScript.
- As the reviewer, I can see CI enforce the same checks on every push.

## Functional requirements
| ID | Requirement |
|---|---|
| F01-FR-01 | Repo layout at least as in `CLAUDE.md` §Repository layout (empty packages get a placeholder `__init__.py`/README) |
| F01-FR-02 | `uv` workspace at root containing `packages/r2r_core` and every Python service as a member. Python 3.12 |
| F01-FR-03 | `docker-compose.yml` with a `postgres` service (16) that creates the DBs `erp_sim`, `lims_sim`, `qms_sim`, `app`, `dagster` through an init script. A named volume `pgdata`. A `./lakehouse` bind mount declared for later services. A health check |
| F01-FR-04 | A shared multi-arch Python base Dockerfile (`docker/python.Dockerfile`), parameterised by service path |
| F01-FR-05 | `frontend/` scaffolded with Vite + React 18 + TS + Tailwind + ESLint + Vitest. It shows a placeholder "R2R Intelligence Demo" page |
| F01-FR-06 | Makefile targets: `up`, `down`, `logs`, `check`, `fmt`, `test`, `e2e` (placeholder), `demo-reset` (placeholder that echoes "not yet implemented"), `pipeline` (placeholder), `scenario` (placeholder) |
| F01-FR-07 | `make check` runs: `ruff check`, `ruff format --check`, `mypy --strict` on every `src/`, `pytest`, `npm run lint`, `npm run typecheck`, `npm test -- --run`, and the leak scan (no-op until F02) |
| F01-FR-08 | Custom lint guard: a pytest-based or ruff-plugin check that fails if `datetime.now(`, `datetime.utcnow(` or `date.today(` appear in any `src/` outside `packages/r2r_core/src/r2r_core/clock.py` |
| F01-FR-09 | GitHub Actions workflow `ci.yml` running `make check` on push/PR (ubuntu-latest, uv cache, npm cache) |
| F01-FR-10 | `.env.example` with every variable in `02-architecture` §6, commented. `.gitignore` covers `.env`, `lakehouse/`, `node_modules`, `.venv`, `.leakscan/denylist.txt` |
| F01-FR-11 | `specs/` folder from this package is committed into the repo unchanged |
| F01-FR-12 | `README.md` with prerequisites (Docker Desktop, uv, Node 20, an Apple Silicon laptop with 16 GB available to Docker), quickstart and command list |

## Acceptance criteria
- **F01-AC-01** Given a clean clone and a copied `.env`, when I run `make up`, then `postgres` becomes healthy and `psql -l` lists the 5 databases.
- **F01-AC-02** When I run `make check` on the fresh repo, then it exits 0.
- **F01-AC-03** Given a file in `services/app_api/src` containing `datetime.now()`, when I run `make check`, then it fails and names the file and line.
- **F01-AC-04** When I push to GitHub, then the CI workflow runs `make check`.
- **F01-AC-05** `docker buildx build --platform linux/arm64,linux/amd64 -f docker/python.Dockerfile .` succeeds.

## Out of scope
Any business logic, real services beyond postgres, and deployment.
