# 00 · Constitution

These principles override every other spec. If a feature spec appears to conflict with one, the constitution wins. Log the conflict in `OPEN_QUESTIONS.md`.

## P1. Live, end to end, visible
Every demo action must travel the real path: a source event, then a pipeline run, then the published contract, then the webhook and queue, then the mirror, then the UI, then (where relevant) an agent. Nothing on screen may be hard-coded or faked. Each hop must be observable: pipeline run in the Dagster UI, queue rows on the Sync Status page, traces on the Agent Trace page.

## P2. The data product owns the numbers. The application owns the people.
- The pipeline derives every **fact** from source data and publishes a **read-only contract** (`published` schema). Facts are stage, stage entry/exit dates, applicable SLAs, locked system need-by date, flags and weekly metrics.
- **Plan dates** depend on human input and on "today": operative need-by, expected completion, SLA compression, RAG, air-gap age. They are computed at read time by the **shared pure library `r2r_core.sla`**, which is deterministic and fully unit-tested. Nowhere else may implement this maths.
- The application **mirrors** the contract into its own database and **never** queries the lakehouse on a user request path.
- Human input (overrides, comments, statuses) lives **only** in the application database, is **versioned**, and is composed with the mirror at read time.
- Nothing is ever written back to the lakehouse or to source systems.
- Exception: metrics whose input signal exists only in the app (human-entered) are computed app-side. The rule follows **where the signal originates**.

## P3. Deterministic core, probabilistic edge
- Stage assignment, SLA maths and metrics are fixed rules over named fields. There is **no model, randomness or inference** in the pipeline. The same inputs always give the same outputs.
- Every derived value carries the ID of the rule that produced it (for example `stage_rule_id`).
- AI agents **only propose**. A proposal must pass a deterministic validator, then be approved by a human with the right role, before any action happens. Agents have read-only tools.
- Every agent step (prompt, tool calls, output, validation result, human decision) is traced.

## P4. Configured, not coded, per site
Stages, SLAs, owning teams, reason codes, molecule types, campaigns, terminology and source adapters are defined in a **site profile** YAML (`config/site-profiles/`). Code reads the profile. Hard-coding a stage name or SLA number outside the profile is a defect.

## P5. Clean-room and client-safe
All data is synthetic, produced by a seeded generator. All names are generic (see domain model §9). The leak scanner runs in `make check` and in CI. Widely used commercial platform names (e.g. SAP) may appear only as site-profile `terms` values and stage labels (03 §9, OQ-075); never in code, data, fixtures or commits.

## P6. Databricks-portable data product
- Transform SQL must use the subset that runs unchanged on **both DuckDB and Spark SQL**. Avoid DuckDB-only functions; use `CASE`, `COALESCE`, `DATE_ADD`/`DATEDIFF` through the macro shim defined in F06, and standard window functions.
- Tables are Delta. Schemas follow `staging`, `intelligence` and `published`.
- Keep the pipeline's six-step shape: `setup → extract → transform → snapshot_aggregate → publish → notify`.

## P7. Resettable, repeatable, rehearsable
- `make demo-reset` returns the whole system to the canonical opening state in under 3 minutes.
- Scenario steps are scripted and idempotent. The same step from the same state always gives the same screen.
- The demo runs fully offline with `LLM_PROVIDER=replay`.

## P8. Quality bar
- Tests first for domain logic (stage engine, SLA maths, compression, metrics, validator).
- `mypy --strict` on Python `src/`, `tsc --noEmit` on the frontend, and zero lint errors.
- Every acceptance criterion in a feature spec maps to at least one automated test, referenced by ID in the test name or docstring.
- The UI must be readable on a 1440×900 screen-share at 100% zoom.

## P9. Small, explicit, explainable
Choose the simplest design that satisfies the spec. Name things for what they are. A non-engineer prospect may look at any file on screen.
