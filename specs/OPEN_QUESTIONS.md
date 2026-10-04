# Open Questions

Add entries as: `## OQ-NNN · <feature> · <date>` then context, question, options, and decision (filled by human).

## OQ-001 · F01 · 2026-10-04
**Context:** The cloned repo has everything under a top-level `r2r-demo-specs/` folder (CLAUDE.md, README.md, `specs/`). CLAUDE.md's layout shows `r2r-demo/` as the root with `specs/` inside it. F01-FR-11 says to commit `specs/` "unchanged", and T9 says "Copy `specs/` in".
**Question:** Where does the scaffold go? Do we build at the repo root and move or copy `CLAUDE.md` and `specs/` up to it, or build inside `r2r-demo-specs/`? Should `r2r-demo-specs/` be kept, renamed or removed afterwards?
**Options:** (a) Scaffold at repo root and `git mv` CLAUDE.md, specs/ and README up to it. (b) Scaffold inside `r2r-demo-specs/`, which becomes the project root. (c) Scaffold at repo root and keep `r2r-demo-specs/` as a read-only reference copy.
**Decision:** Repo root is the clone root (`demo_takeda_r2r/`). First commit moves `CLAUDE.md`, `specs/` and `.claude/` (if present) to the root with `git mv`, then deletes `r2r-demo-specs/` (its README is not needed). Scaffold is built at the root. *(Note: no `.claude/` directory existed in the clone, so nothing to move.)*

## OQ-002 · F01 · 2026-10-04
**Context:** F01-FR-02 says every Python service is a uv workspace member. The plan says "add members as their features create them". F01-FR-01 says empty packages get only a placeholder `__init__.py`/README. A uv workspace glob such as `services/sources/*` fails if a matched folder has no `pyproject.toml`.
**Question:** Does F01 give every service and tool a minimal `pyproject.toml` and `src/<pkg>/__init__.py`, so that `mypy --strict` on "every `src/`" covers them? Or does it list only `r2r_core` and add members later? Is `tools/checks` a workspace member? That is where the clock-guard test lives, and it has no `src/`.
**Decision:** Explicit workspace members list; add each member only once its package exists. In F01: `packages/r2r_core` plus any tool packages created. FR-02 describes the end state.

## OQ-003 · F01 · 2026-10-04
**Context:** The clock guard differs between sources. F01-FR-08 and CLAUDE.md name `datetime.now`, `datetime.utcnow` and `date.today`. The plan also bans `time.time`. Agent traces record `latency_ms`, and the sync worker needs "now − 5 min" for stale claims. Neither is specified.
**Question:** Is `time.time` banned? Are `time.monotonic` and `time.perf_counter` allowed for latency measurement? Which clock does the drain worker's `claimed_at` and stale-claim check use (demo clock or wall clock)? Are `tools/` and test code covered by the guard, or only `src/`?
**Decision:** Guard bans `datetime.now`, `datetime.utcnow`, `date.today`, `time.time`. `time.monotonic` and `time.perf_counter` are allowed for latency/duration measurement. Infrastructure timing done in SQL (e.g. the worker's stale-claim check using Postgres `now()`) is allowed. Business time must use `r2r_core.clock`. The rule is written into the guard's docstring.

## OQ-004 · F01 · 2026-10-04
**Context:** The CLAUDE.md "Commands (created in F01)" list includes `e2e-headed`, `record-agents`, `doctor`, `record-video` and `make demo-reset` timing. F01-FR-06 lists only `up, down, logs, check, fmt, test, e2e, demo-reset, pipeline, scenario`. `make scenario STEP=<id>` also needs a placeholder that tolerates the argument.
**Question:** Does F01 add placeholder targets for `e2e-headed`, `record-agents`, `doctor` and `record-video`? What should `make doctor` check in F01 (Docker, uv, Node 20, RAM)?
**Decision:** Add `e2e-headed`, `record-agents`, `doctor`, `record-video`, `fmt`, `test` and `logs` now. Targets without an implementation echo "not yet implemented (Fxx)" naming the implementing feature.

## OQ-005 · F01 · 2026-10-04
**Context:** F01-AC-02 requires `make check` to exit 0 on a fresh repo. By default `pytest` exits 5 when no tests are collected, and `vitest --run` fails with no test files. The `integration` marker split is in the plan, but F01 has no integration tests. F01-AC-01 (`psql -l` lists 5 DBs) needs Docker and has no assigned test or job.
**Question:** Confirm the intended handling: a trivial passing test in each Python package and the frontend, plus `--passWithNoTests` or equivalent? Should AC-01 be a scripted integration test (marked `integration`, run in the CI postgres job) or a manual check recorded in the PR?
**Decision:** Ship minimal passing tests: an r2r_core smoke test, the clock-guard tests, one Vitest smoke test. AC-01 gets a pytest marked `@pytest.mark.integration` that connects to Postgres and asserts the 5 databases exist; it runs in the CI integration job with a Postgres service, and `make check` skips it.

## OQ-006 · F01 · 2026-10-04
**Context:** F01-AC-05 requires a multi-arch `docker buildx build`. FR-04 says the Dockerfile is "parameterised by service path", but no services exist yet. Building `linux/amd64` on an Apple Silicon laptop needs QEMU emulation. CI (F01-FR-09) runs `make check` only, so AC-05 is not enforced.
**Question:** What is the default build arg when no service exists (the `r2r_core` package only)? Is AC-05 verified manually, or should CI gain a buildx job?
**Decision:** Dockerfile takes build-arg `SERVICE_PATH` (default `packages/r2r_core`) and installs that member with uv. F01 builds the default as a smoke target. AC-05 verified locally with `docker buildx` (output pasted in the PR). CI builds `linux/amd64` only.

## OQ-007 · F01 · 2026-10-04
**Context:** `.env.example` must contain every variable from 02-architecture §6, but that list shows `POSTGRES_*` as a wildcard and gives no values for the secrets (`WEBHOOK_SECRET`, `SCENARIO_TOKEN`) or for `CLOCK_SOURCE`/`SITE_PROFILE` defaults. The Postgres init script needs a user and password.
**Question:** Which exact `POSTGRES_*` names should be used (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`)? Should secrets get obvious dev-only placeholder values, so `cp .env.example .env && make up` works, as F01 story 1 and AC-01 imply?
**Decision:** `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`, `POSTGRES_USER=r2r`, `POSTGRES_PASSWORD=r2r_dev_only`, plus a per-DB DSN pattern documented in a comment. `WEBHOOK_SECRET=dev-only-change-me`, `SCENARIO_TOKEN=dev-only-change-me`. `ANTHROPIC_API_KEY` left empty. Every variable has a comment naming the feature that uses it.

## OQ-008 · F01 / specs · 2026-10-04
**Context:** Duplicated or garbled text in the shared specs. (1) `04-data-contracts.md` §3 repeats the "Derivations (non-obvious columns)" table twice. (2) §4.2b `weekly_metric_rows_v` appears twice. (3) §4.1 lists `lims_rejected` twice. It is also unclear whether `lims_rejected` is already a `batch_flat` business column. (4) `03-domain-model.md` §7 repeats two sentences, and the line "For the others, `metric_reference_v.status = 'awaiting_signal'`…" has lost its subject. It presumably refers to metrics with `computed_in: app`. Separately, F01-FR-11 requires committing `specs/` "unchanged".
**Question:** Should these be fixed in the specs now, or left untouched until F01 is done (because of "unchanged")? I can't resolve (4) without the human confirming that "the others" means the `computed_in: app` metrics M1, M2, M4 and M5.
**Decision:** **Resolved upstream (2026-10-04).** `03-domain-model.md` and `04-data-contracts.md` were replaced with corrected versions: duplicated blocks removed, `lims_rejected` listed once, §7 reworded ("For metrics with `computed_in: app`…"). Committed separately as `docs(specs): fix duplicated blocks (OQ-008)`.

## OQ-009 · F01 · 2026-10-04
**Context:** CLAUDE.md says to commit once per task and stop for review at the end. F01 T9 says to "record the AC→test table in the PR description". The workflow does not say whether work happens on a branch, or whether Claude opens the PR.
**Question:** Which branch should F01 commit to (e.g. `feat/F01-repo-foundation`)? Should I open the PR with `gh`, or only prepare the AC→test table for you?
**Decision:** Work on branch `feat/F01-repo-foundation`, one commit per task. Push, then open a PR with `gh` if installed and authenticated (otherwise stop and tell the human). PR description includes the AC → test table and the buildx output. Human reviews and merges; Claude does not merge.
