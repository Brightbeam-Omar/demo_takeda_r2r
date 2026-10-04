# 01 · Product Overview (PRD)

## 1. Purpose
A working demonstration of **R2R Intelligence**: a system that replaces a manual, spreadsheet-run Receipt-to-Release process (incoming raw materials moving from goods receipt through sampling, QC testing and QA release) with:

1. a governed **data product** that derives batch status and SLA metrics from systems of record;
2. a **live application** for the daily huddle: exceptions first, role-aware, with audited human input;
3. an **orchestration harness** of AI agents that do the cross-system legwork a person does today, inside a deterministic governance boundary.

Its job is to persuade pharma manufacturing, quality and digital leaders that this is reusable, production-grade capability that can be configured per site. It should not look like a prototype.

## 2. Audiences
| Audience | What they need to see |
|---|---|
| Site digital delivery manager, quality/supply SMEs | Their process modelled faithfully, real edge cases, under-the-hood mechanics, how it fits their stack (ERP, LIMS, QMS, lakehouse) |
| Global digital/manufacturing leadership | Value (batch release speed, avoided failed batches, working capital), governance, scalability across sites, a five-minute "aha" |

## 3. Personas (also the RBAC roles in the demo)
| Persona | Role key | Can |
|---|---|---|
| **Pat, Supply Planner** | `planner` | View everything. Set adjusted need-by dates with reason codes and expedite flags. Add comments |
| **Quinn, QC Lead** | `qc_lead` | View everything. Set manual RAG status and comments. Approve QC-related agent proposals |
| **Alex, QA Release Lead** | `qa_release` | View everything. Set manual RAG status and comments. Approve QA-related agent proposals (e.g. air-gap tickets) |
| **Sam, Site Lead** | `viewer` | Read-only. All write controls hidden, and server rejects writes with 403 |
| **Admin** | `admin` | Everything, plus SLA/profile configuration and demo controls |

## 4. The problem being dramatised
- A 40-tab spreadsheet tracker is simultaneously the system of record, reporting engine and data-entry surface for a ~30-person weekly huddle.
- Status is typed in by hand and decays as soon as the meeting ends. Last save wins. There is no audit trail.
- KPIs are rebuilt by hand. Senior SMEs spend time on derivation rather than judgement.
- Gaps between systems (e.g. LIMS approved but ERP not released) are found late or not at all.
- Tacit knowledge (supplier quirks, handover notes) never reaches the record.

## 5. Scope
### Tier 1, "Call-ready" (detailed specs F01–F14)
Foundation and leak scan, site profile, synthetic data, ERP/LIMS/QMS simulators, pipeline (stage engine, metrics M3/M6/M7, published contract, webhook), sync layer (webhook → queue → drain → mirror, watermark), application API (read, overrides, audit, RBAC), Overview UI, dual-date editing with SLA compression, batch history and "Explain this number", Sync Status page, Air-gap agent with human approval and trace, scenario engine and demo reset, run-of-show E2E test.

### Tier 2, "Full solution" (outline specs T2-xx)
Metrics M1/M2/M4/M5 via 3PL feed and SME inputs; safety poll self-heal and ops console; release-readiness, tacit-signal and briefing agents; agent registry, eval harness and cost meter; S/4-style adapter, spreadsheet ingest and site profile switch; value calculator; OpenLineage/Marquez; PySpark runner and portability test; AWS deployment.

### Out of scope
Real integrations with any customer system. Real SSO. Writes to any source system. GxP validation. Mobile layouts.

## 6. Run-of-show (the acceptance test for the whole product)
| # | Act | Must work |
|---|---|---|
| 1 | The problem | Download/open the generated legacy tracker workbook (Tier 2 adds ingest; Tier 1 just shows it) |
| 2 | Monday morning | Overview loads in < 2 s. Exceptions first. Persona switch changes allowed actions |
| 3 | Under the hood | Run step `lims-approve-B1042` (Demo Controls) → pipeline run visible in Dagster → webhook row on Sync Status → mirror updated → batch moves stage in UI within 90 s of running the step. "Explain this number" traces a metric to rule and source rows |
| 4 | Resilience | (Tier 2) Webhook disabled → safety poll converges |
| 5 | Human judgement | Planner pulls B2077 need-by forward 7 days (2026-12-03 → 2026-11-26) with reason → compression 6/37/6 → expected 15 Oct → 14 Oct, green → amber → re-sort → audit entry |
| 6 | The harness | Air-gap agent proposes a QA ticket with evidence → validator passes → QA approves → action logged → trace viewable |
| 7 | Trust | (Tier 2) Registry, evals, cost |
| 8 | Your world | (Tier 2) Profile switch, value calculator |

## 7. Success criteria (Tier 1)
- `make demo-reset && make e2e` passes on a clean Apple Silicon Mac with 16 GB available to Docker, offline, with `LLM_PROVIDER=replay`.
- Acts 2, 3, 5 and 6 run in under 25 minutes total, with no manual database edits.
- Leak scanner reports zero findings.
- A new engineer can run the demo from the README in under 15 minutes.
