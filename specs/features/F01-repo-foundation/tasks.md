# F01 · Tasks
- [ ] T1 Create directory layout, root README stub, `.gitignore`, `.env.example`
- [ ] T2 Root `pyproject.toml` uv workspace, `packages/r2r_core` skeleton with a trivial passing test
- [ ] T3 Ruff + mypy config. `make fmt` and `make check` (Python part)
- [ ] T4 [TDD] Wall-clock guard test (F01-FR-08) with a fixture file proving it fails (F01-AC-03)
- [ ] T5 `docker/python.Dockerfile` (multi-arch, uv-based install) and `docker-compose.yml` with postgres + init SQL (F01-AC-01, AC-05)
- [ ] T6 Frontend scaffold with Tailwind, ESLint, Vitest and placeholder page. Wire into `make check`
- [ ] T7 Remaining Makefile targets (placeholders where noted)
- [ ] T8 GitHub Actions `ci.yml` (unit job + integration job with postgres service)
- [ ] T9 Copy `specs/` in. Finish README quickstart. Verify every AC and record the AC→test table in the PR description
