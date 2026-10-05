# 06 · Development Roadmap

Status values: `draft` (spec not build-ready) · `ready` · `in_progress` · `review` (built, awaiting human) · `done`.
Claude Code updates `in_progress` and `review`. Only the human sets `done`.

## 1. Milestones (Tier 1)

| Milestone | Features | Outcome you can see | Est. effort* |
|---|---|---|---|
| **M0 Foundation** | F01, F02, F03 | `make up` and `make check` green. Profile, clock and SLA library fully tested | 2–3 days |
| **M1 Sources & data** | F04, F05 | Simulated ERP/LIMS/QMS populated with ~700 realistic rows and 5 story batches | 2–3 days |
| **M2 Data product** | F06, F07 | Dagster run produces the published contract and fires the webhook | 3–4 days |
| **M3 Application core** | F08, F09 | Mirror syncs automatically. API serves composed rows, overrides, audit, RBAC | 3 days |
| **M4 Experience** | F10, F11 | Overview, editing, batch drawer, Explain, Sync Status and Audit pages | 4–5 days |
| **M5 Harness** | F12 | Air-gap agent: propose, validate, approve, act, trace (replay + live) | 3 days |
| **M6 Demo-ready** | F13, F14 | `make demo-reset`, scripted scenario steps, Playwright run-of-show, README | 2 days |

\* Elapsed days with one engineer driving Claude Code and reviewing at each feature gate. That comes to roughly **19–23 working days**, about 4 weeks for one person or about 2 weeks for two people working in parallel (see §3).

## 2. Feature register

| ID | Feature | Depends on | Tier | Status |
|---|---|---|---|---|
| F01 | Repo foundation & tooling | n/a | 1 | done |
| F02 | Leak scanner | F01 | 1 | done |
| F03 | Core library: site profile, demo clock, SLA maths | F01 | 1 | done |
| F04 | Source simulators & clock service | F03 | 1 | done |
| F05 | Synthetic data generator & story batches | F04 | 1 | done |
| F06 | Pipeline I: extract, flatten, stage engine | F05 | 1 | done |
| F07 | Pipeline II: snapshot, metrics, publish, notify (Dagster) | F06 | 1 | done |
| F08 | Sync layer: webhook, queue, drain, mirror | F07 | 1 | done |
| F09 | Application API: reads, overrides, audit, RBAC, explain | F08 | 1 | done |
| F10 | Frontend shell & Overview | F09 | 1 | done |
| F11 | Editing, batch drawer, Explain, Sync & Audit pages | F10 | 1 | ready |
| F12 | Agent harness & Air-gap agent | F09 (API), F11 (UI tasks) | 1 | ready |
| F13 | Scenario engine & demo reset | F07, F09, F10, F12 | 1 | ready |
| F14 | Run-of-show E2E, README, rehearsal kit | all Tier 1 | 1 | ready |
| T2-01 | 3PL feed, delivery entry, metrics M1/M2/M4/M5 | Tier 1 | 2 | draft |
| T2-02 | Safety poll self-heal, ops console, alerts | Tier 1 | 2 | draft |
| T2-03 | Release-readiness agent | F12 | 2 | draft |
| T2-04 | Tacit-signal agent & unstructured corpus | F12 | 2 | draft |
| T2-05 | Huddle / leadership briefing agent | F12 | 2 | draft |
| T2-06 | Agent registry, eval harness, cost meter | F12 | 2 | draft |
| T2-07 | S/4-like adapter, spreadsheet ingest, site profile switch | Tier 1 | 2 | draft |
| T2-08 | Value calculator | Tier 1 | 2 | draft |
| T2-09 | Lineage (OpenLineage/Marquez) & PySpark portability | F07 | 2 | draft |
| T2-10 | AWS deployment | Tier 1 | 2 | draft |

## 3. Parallel tracks (if two people drive Claude Code)
- **Track A (data):** F03 → F04 → F05 → F06 → F07
- **Track B (app):** F01/F02 → F08 against a **fixture contract** (hand-written Delta files matching `04-data-contracts` §4, written to `LAKEHOUSE_PATH`) → F09 → F10 → F11 → F12
- **Join:** when F07 is `done`, swap the fixture for the real pipeline output, re-run F08–F12 tests, then build F13 → F14.
- Track B needs F03 (core library) and F04's `demo_clock` migration. Do those first, or have Track B stub them.

## 4. Definition of Done (every feature)
1. All tasks ticked. All AC in `spec.md` covered by named automated tests.
2. `make check` green. No new `# type: ignore` or `eslint-disable` without a justification comment.
3. No leak-scan findings. No hard-coded stage names or SLA numbers outside the profile (grep check).
4. README / `.env.example` updated if behaviour or config changed.
5. Demo path still works: `make demo-reset && make e2e` (from F14 onward).
6. Human review: run it, read the diff, set `done`.

## 5. Review gates (human)
| After | Check |
|---|---|
| F03 | SLA maths test cases match `03-domain-model` §5.7. Read them; they are the business logic |
| F05 | Open the generated data and legacy workbook. Does it look like a real site? Ask the domain SME to sanity-check the 5 story batches |
| F07 | Inspect `published.*` with DuckDB. Stage counts plausible? Metrics plausible? |
| F11 | Screen-share rehearsal of acts 2, 3 and 5 at 1440×900 |
| F12 | Read the agent prompts and validator rules. Check the evidence quality |
| F14 | Full dry run with the presenter and SME |

## 6. Driving Claude Code (prompt templates)

**Start a feature**
> Read CLAUDE.md, then specs/00, 03, 04, 06 and specs/features/F0X-*/. Summarise the feature in 5 bullets, list any ambiguities (add them to OPEN_QUESTIONS.md), then wait for my go-ahead before writing code.

**Build**
> Go. Implement F0X tasks in order, test-first where marked [TDD]. Run `make check` after each task and commit per task. Stop when all tasks are done and report AC coverage as a table (AC ID → test name).

**Review fix**
> Review feedback on F0X: <points>. Fix them, keep the commits small, re-run `make check`, then update the table.

**Resume**
> Read CLAUDE.md and specs/06-roadmap.md. Continue F0X from the first unticked task in tasks.md.
