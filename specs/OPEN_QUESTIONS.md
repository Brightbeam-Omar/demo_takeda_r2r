# Open Questions

Add entries as: `## OQ-NNN · <feature> · <date>` then context, question, options, and decision (filled by human).

## OQ-001 · F01 · 2026-10-04
**Context:** The cloned repo has everything under a top-level `r2r-demo-specs/` folder (CLAUDE.md, README.md, `specs/`). CLAUDE.md's layout shows `r2r-demo/` as the root with `specs/` inside it. F01-FR-11 says to commit `specs/` "unchanged", and T9 says "Copy `specs/` in".
**Question:** Where does the scaffold go? Do we build at the repo root and move or copy `CLAUDE.md` and `specs/` up to it, or build inside `r2r-demo-specs/`? Should `r2r-demo-specs/` be kept, renamed or removed afterwards?
**Options:** (a) Scaffold at repo root and `git mv` CLAUDE.md, specs/ and README up to it. (b) Scaffold inside `r2r-demo-specs/`, which becomes the project root. (c) Scaffold at repo root and keep `r2r-demo-specs/` as a read-only reference copy.
**Decision:** Repo root is the clone root. First commit moves `CLAUDE.md`, `specs/` and `.claude/` (if present) to the root with `git mv`, then deletes `r2r-demo-specs/` (its README is not needed). Scaffold is built at the root. *(Note: no `.claude/` directory existed in the clone, so nothing to move.)*

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

## OQ-010 · F02 · 2026-10-04
**Context:** F02-FR-02 says env `LEAKSCAN_DENYLIST` holds the denylist content, newline-separated. But `.env.example` (F01, following 02-architecture §6) sets `LEAKSCAN_DENYLIST=.leakscan/denylist.txt`, which reads as a file path. Copied into `.env` as is, the scanner would treat the string `.leakscan/denylist.txt` as a term. A multi-line value also does not fit well in a one-line `.env` entry or in docker `env_file`.
**Question:** Is the env var the denylist *content* (as F02-FR-02 says, and as a GitHub secret naturally is) or a path? If content, F01's `.env.example` entry should become an empty, commented placeholder. Is the order a fallback (env wins, the file is ignored) rather than a merge of both?
**Decision:** `LEAKSCAN_DENYLIST` holds the denylist *content*, not a path. Removed from `.env.example` and replaced by a comment ("CI only, set as a GitHub secret; locally use .leakscan/denylist.txt"). Safety net: if the env value is a single line that is an existing file path, exit 2 with a clear message. Env wins over the file (fallback, no merge).

## OQ-011 · F02 · 2026-10-04
**Context:** F02-FR-07 has CI read the denylist from the secret `LEAKSCAN_DENYLIST`, and F02-AC-03 / FR-02 make a missing denylist exit 1 when `CI=true`. The F01 `check` job has no secret wired in. Until the secret exists, and always for PRs from forks (secrets are not exposed to them), `make check` would fail in CI.
**Question:** Is it OK that CI is red until the human creates the secret? Should fork PRs be exempt? Which `CI` values count as true (`true` only, or `1`/`true`, case-insensitive)? Does F02 edit `.github/workflows/ci.yml` to pass `secrets.LEAKSCAN_DENYLIST` to the `check` job, and to the `integration` job too (it does not run `make check`)?
**Decision:** Wire the scanner into the `check` CI job only, with `CI=true` and the secret mapped to the env var. A missing secret in CI exits 1 by design; the human creates the secret before merge. The repo is private with no forks, so fork PRs are ignored. The `integration` job does not need it. (Implementation choice: `CI` counts as true for `true` or `1`, case-insensitive.)

## OQ-012 · F02 · 2026-10-04
**Context:** FR-03 says matching is "case-insensitive on word boundaries", with `\b` in the plan. `\b` does not work next to non-word characters. Denylist entries like `acme-real-client`, an email domain (`@client.example`) or a term ending in `.` or `-` would fail to match at those edges. FR-03 also does not say whether plain terms are regex-escaped (they should be), or what a "term" is for rule numbering and masking.
**Question:** Confirm the matching rules. Proposed: plain terms are `re.escape`d and bounded with `(?<!\w)…(?!\w)`; `re:` entries are used as written, case-insensitive. `rule #n` is the 1-based position among non-blank, non-comment entries in the active denylist. The masked output is first letter + `***` of the *matched text*.
**Decision:** No `\b`. Plain terms are `re.escape`d and wrapped as `(?<![A-Za-z0-9])<term>(?![A-Za-z0-9])`, case-insensitive. `re:` entries are used as written, case-insensitive, with no added boundaries. Rule number = 1-based index among non-blank, non-comment entries. Mask = first character of the matched text + `***`.

## OQ-013 · F02 · 2026-10-04
**Context:** FR-04 says parquet is scanned by **column names**; the plan says schema **plus the first 1000 rows of string columns**, and the same for Delta. FR-04 also says "Delta table data under any test fixture folder" while the plan uses `**/fixtures/**`. Delta tables are directories (parquet files plus `_delta_log` JSON), and the repo ignores `lakehouse/`. A leak in row 1001 or later would not be caught.
**Question:** Which is authoritative: names only, or names plus first 1000 rows? Should the row cap be removed (fixtures are small) or kept? Is `**/fixtures/**` the exact Delta location rule? Does `_delta_log` JSON get scanned as plain json (it contains schema column names and file paths)?
**Decision:** Scan parquet and Delta column names and all rows of string columns, no row cap. Print a warning if a single file is over 200 MB.

## OQ-014 · F02 · 2026-10-04
**Context:** FR-01 scans "all git-tracked text files (plus staged files)". `git ls-files` omits new files that are not yet `git add`ed. It lists tracked files that were deleted from disk. The plan skips non-text files "except the supported readers", so `.docx`, `.pptx`, `.pdf` and images are silently skipped. File and directory *names* are not scanned. Commit messages and branch names are not scanned either, although CLAUDE.md's hard rule says no client names "in commits".
**Question:** (a) Warn (not fail) on skipped binary files, so nothing is silently unscanned? (b) Also scan file paths? (c) Add a CI step that scans commit messages and the branch name (`git log`) as a separate feature, or leave out of F02? (d) Should untracked, non-ignored files be scanned locally?
**Decision:** No path args: scan git-tracked, staged and untracked-but-not-ignored files. File paths are scanned as well as contents. `.docx`, `.pptx`, `.xlsx` are scanned by reading the text inside the archive. Other binaries (`.pdf` etc.) are skipped, listed in a final "skipped N binary files" summary, and do not fail. `--commits <rev-range>` scans commit messages and author names; CI runs it on the PR or push range, and `make check` runs it on `@{u}..HEAD` (skipped when there is no upstream).

## OQ-015 · F02 · 2026-10-04
**Context:** FR-08 allow-list entries are `path:term-hash` with a SHA-256 of the lowercase term. For `re:` rules there is no single "term", so the hash input is unclear (the regex source? the matched text lowercased?). Paths for xlsx hits could be the file, or `file#sheet!cell`. It is also not said whether globs are allowed, whether `#` comments and blank lines are allowed, and whether the path is repo-relative with `/` separators.
**Question:** Hash the lowercased *matched text* (so it works for plain and regex rules alike)? Match on the repo-relative file path only (every occurrence of that term in that file is allowed)? Support `#` comments? No globs?
**Decision:** Allow entry format: `<repo-relative posix path>:<sha256 hex of the lowercased matched text>`. Works for regex rules too. No globs. Forward slashes.

## OQ-016 · F02 · 2026-10-04
**Context:** FR-01 says `python -m leakscan [paths…]`. The meaning of `[paths…]` is not given: a filter within the tracked files, or arbitrary paths to scan (including untracked and outside a git repo)? Tests (AC-01, AC-02) need to scan temp directories that are not git repos. The workspace also needs `tools/leakscan` added as a member with `src/leakscan` (mypy `--strict`) and new dependencies (`openpyxl`, `pyarrow`, `deltalake`).
**Question:** With no args, scan the repo's tracked and staged files. With paths, scan exactly those files or directories (walked recursively, no git needed)? Are the new dependencies approved for the dev environment and the Docker image (they are scanner-only, so the image need not include them)?
**Decision:** With `[paths…]`: scan exactly those files or directories, recursively, regardless of git. Tests use this on temp dirs, later on `artifacts/`. With none: the default set from OQ-014. `openpyxl`, `pyarrow` and `deltalake` are approved as dependencies of `tools/leakscan` only.
