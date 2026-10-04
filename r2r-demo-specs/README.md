# R2R Intelligence Demo: Spec Package (for Claude Code)

This package is the **specification** for building the R2R Intelligence Demo using spec-driven development with Claude Code. It contains no code. Claude Code builds the code from it.

## What's inside
```
CLAUDE.md                       → goes at the repo root; Claude Code reads it automatically
specs/
  00-constitution.md            → non-negotiable principles
  01-product-overview.md        → PRD: purpose, personas, scope, run-of-show, success criteria
  02-architecture.md            → services, ports, flows, interfaces, ADRs
  03-domain-model.md            → stages, SLA maths, metrics, flags (the business logic)
  04-data-contracts.md          → source schemas, lakehouse layout, published contract, app DB
  05-ux-guidelines.md           → visual system, layout, components
  06-roadmap.md                 → milestones, feature register/status, DoD, review gates, prompts
  OPEN_QUESTIONS.md             → Claude Code logs ambiguities here
  adr/                          → new architecture decisions get recorded here
  features/F01…F14/             → Tier 1: spec.md + plan.md + tasks.md (build-ready)
  features/T2-01…T2-10/         → Tier 2: outline spec.md (detail before building)
```

## How to start
1. Create an empty private repo `r2r-demo` and copy `CLAUDE.md` and `specs/` into its root.
2. Create `.leakscan/denylist.txt` locally (gitignored, see F02) with the reference client's terms. Add the same list as GitHub secret `LEAKSCAN_DENYLIST`.
3. Open Claude Code in the repo and use the prompt templates in `specs/06-roadmap.md` §6, beginning with F01.
4. Review at each feature gate (`06-roadmap.md` §5), then set the status to `done`.

## Before you start: decisions baked into these specs
- Local-first (docker-compose on a 32 GB Apple Silicon Mac). AWS later (T2-10).
- Open-source, Databricks-compatible data product (DuckDB + Delta + Dagster). Spark/Databricks port is in T2-09.
- FastAPI backend (ADR-003). React + Vite frontend.
- LLM via a gateway: `replay` (offline, default for demos), `anthropic` (live), `bedrock` (AWS, later).
