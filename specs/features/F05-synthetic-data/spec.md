# F05 · Synthetic Data Generator & Story Batches

## Context
The demo's credibility depends on data that *feels* like a real site: messy, uneven, with the edge cases SMEs recognise. All of it is generated, deterministic from a seed, and generic.

## Functional requirements
| ID | Requirement |
|---|---|
| F05-FR-01 | `python -m datagen generate --profile site_a --seed 4242` wipes the three source DBs and populates them **only through the F04 event functions** (no raw SQL inserts), replaying a history of ~26 weeks ending at `demo.start_datetime` |
| F05-FR-02 | Volumes (±10%, and each may rise by up to 40% so that FR-03/FR-04 are met; the report states the actual counts, per batch and per lot): 300 materials (≈85% drug_substance, 15% consumable; molecule types 55/25/20 small/large/peptide), 40 suppliers, 6 storage locations (4 onsite, 2 3PL), ~650 distinct batches, of which ~120 carry a re-eval (`09`) lot (so ~770 lots; ordinary re-eval batches have 0–2 previous re-evals, B4410 has 3; receipts before the 26-week window are allowed), ~90 deviations (≈20% open), 5 campaigns `CMP-ALPHA…EMBER` |
| F05-FR-03 | The stage distribution at demo start applies to **open rows** (every lot, `01` and `09`, not `released`), each within ±3 percentage points: pending 3% (receipts reversed same-day and not re-received; see domain model §4), receipt 8%, call_off 12%, sampling 18%, qc_ship 3%, qc_testing 42%, qa_release 14%. A backlog beyond SLA is intended. RAG among open rows (±5 pp): ~55% green, ~25% amber, ~20% red. Released rows are whatever the history produces. ~30% of deliveries go to a 3PL. ~12% of tests are offsite. All targets live in `params.yaml` |
| F05-FR-04 | Durations drawn per stage from lognormal distributions centred near the SLA. ~75–85% on-time historically. Arrivals must give at least 10 completions per week for each of M3, M6 and M7 across the 12 metric weeks, with weekly on-time between roughly 65% and 95% |
| F05-FR-05 | Realism quirks, each present at least 3 times (GR reversal is met by the pending rows): GR reversal same day (101+102); batch with no demand (no need-by); consumable in testing (inflates counts); `erp_blocked` stock; `on_hold` batch; rejected UD; air-gap (LIMS approved > 24 h, no UD); open deviation on a batch in QA Release; failed inbound check; material with two concurrent batches and two open demand rows for different campaigns (both batches show the earliest row's campaign; the report states this Tier 1 limitation) |
| F05-FR-06 | **Five story batches** with fixed IDs, created deterministically regardless of seed (see table below) |
| F05-FR-07 | `python -m datagen legacy-workbook --out artifacts/legacy_tracker.xlsx` exports a deliberately messy "legacy tracker" workbook from the same data: ~12 tabs (Tracker, Call-Off, Sampling Plan, QC Queue, KPI Weekly, Re-Evals, Deviations, Campaign Notes, Lookups, Old, Copy of Tracker, Sheet3), merged headers, colour fills, typed-in statuses that **disagree** with source for ~8% of rows, comments in cells |
| F05-FR-08 | Output report `artifacts/datagen_report.md`: counts by table (per batch and per lot), open-row stage distribution, RAG mix, weekly completions and on-time % for M3/M6/M7, quirk counts (with the Tier 1 campaign limitation), and story batch IDs |
| F05-FR-09 | Same seed → byte-identical DB dumps (excluding sequence-generated surrogate IDs) |
| F05-FR-11 | Write `artifacts/expected_stages.csv` (`row_key, intended_stage, story_id`) as a sidecar oracle. It is **not** loaded into any source DB. F06 uses it to verify the stage engine |
| F05-FR-10 | All names from `03-domain-model` §9 vocabulary. Material descriptions from a generic list ("Excipient 017", "API Intermediate 004", "Buffer Salt 012", "Filter Capsule 0.2µm 003") |

### Story batches
| ID | Material | Setup at demo start | Used in |
|---|---|---|---|
| `B1042` | RM10023 API Intermediate 004 (small molecule, CMP-ALPHA) | QC testing onsite, all tests done, LIMS **not yet** approved. Scenario step approves it | Act 3: move to QA Release |
| `B2077` | RM10031 Excipient 017 (peptide, CMP-BRAVO, supplier SUP007) | Onsite delivery, onsite test, lot 01, **sampling entry 2026-10-08**, locked system need-by **2026-12-03** (A=56=B → no compression; expected 2026-10-15, green), full_spec | Act 5: planner pulls forward 7 days → compression |
| `B3150` | RM10045 Buffer Salt 012 (large molecule, CMP-CEDAR) | QA Release with an **open major deviation** | Deviation popup / blocked release |
| `B4410` | RM10052 Excipient 021 (small molecule) | Re-eval lot 09 in sampling. Batch history shows initial release plus 3 previous re-evals | Batch history |
| `B5003` | RM10067 API Intermediate 009 (small molecule, CMP-ALPHA) | LIMS approved **30 h** before demo start, no UD → air gap | Act 6: air-gap agent |

Story dates are offsets from `demo.start_datetime`; the absolute values below are the site_a values and are asserted in tests. Story material and batch IDs are reserved (the world builder skips them). Fixed values live in `stories.py`. `test_result` rows are seeded for story batches only. B1042: five tests, all `pass`, sample `in_progress`. B3150: open major deviation only (no hold, no block). B4410: previous re-evals at 8, 16 and 24 weeks before the open lot, all released. B2077: sampling entry = start −4 days, need-by = start +52 days. B5003: approved start −30 h (Sunday 02:00 local).

## Acceptance criteria
- **F05-AC-01** Running generate twice with seed 4242 gives identical dumps (FR-09).
- **F05-AC-02** The report shows volumes, the open-row stage distribution (±3 pp) and the RAG mix (±5 pp) within tolerances (FR-02, FR-03), and >= 10 weekly completions for M3/M6/M7 (FR-04), computed from the generator's **intended stage** labels (FR-11).
- **F05-AC-03** Each quirk in FR-05 occurs ≥ 3 times.
- **F05-AC-04** All five story batches exist with the exact setup described.
- **F05-AC-05** The legacy workbook opens in Excel/LibreOffice, has ≥ 12 tabs, and ~8% status disagreement versus source.
- **F05-AC-06** The leak scan on generated artefacts is clean.
- **F05-AC-07** Generation completes in < 60 s on the target laptop.
