# 03 · Domain Model

This is the single source of truth for R2R business logic. Every value below that varies by site lives in the **site profile** (§2). All the defaults here are the values for `site_a`.

## 1. Glossary
| Term | Meaning |
|---|---|
| Material | A purchased input identified by a material number (e.g. `RM10023`). Has a **class** (`drug_substance`, `consumable`) and a **molecule type** (`small_molecule`, `large_molecule`, `peptide`) |
| Batch | A supplier delivery of a material, identified by batch number (e.g. `B1042`). One supplier batch maps to one internal batch |
| Inspection lot | A quality inspection of a batch. `lot_type` `01` = initial receipt inspection, `09` = re-evaluation (periodic retest). A batch may have several lots over time |
| Goods receipt (GR) | ERP posting that the batch was received (into a 3PL or onsite location) |
| 3PL | Third-party logistics warehouse. Material held at a 3PL must be **called off** (transferred) to site before sampling |
| Inbound check | Receipt-time documentation/visual check. Outcome `open`, `passed`, `resolved` (completed with an issue resolved; F19) or `failed` |
| Sample | LIMS sample taken for a lot. May be tested onsite or **offsite** at an external lab |
| LIMS approval | All tests for the lot complete and approved in LIMS |
| Usage decision (UD) | ERP quality decision closing the lot: accept (release), reject or cancel |
| Need-by date | Date the material is needed by production (from ERP MRP demand) |
| Campaign | Production campaign that consumes the material (from demand) |
| Air gap | LIMS approved but the result never transferred to the ERP (no interface record, no usage decision) after the threshold. Release is stuck between systems. A normal QA Release lot, whose results were recorded in the ERP, is not an air gap |

## 2. Site profile (YAML)
Loaded by `r2r_core.profile.load_profile()`. It is validated with Pydantic, and an invalid profile fails startup.

```yaml
site:
  code: SITE_A
  name: "Site A – Harbourview"
  timezone: Europe/Dublin
demo:
  start_datetime: "2026-10-12T08:00:00+01:00"   # canonical opening: a Monday morning
  seed: 4242
stages:            # sort order = list order; key is stable and used in code/data
  - {key: pending,     label: "Pending",      sla_days: 0,  team: "Logistics",     action: "Awaiting goods receipt", show_card: false}   # show_card (default true): F17, stage card on the Overview
  - {key: receipt,     label: "Receipt",      sla_days: 10, team: "Warehouse",     action: "Complete inbound check"}
  - {key: call_off,    label: "Call Off",     sla_days: 5,  team: "Warehouse",     action: "Call off from 3PL to site", applies_if: "received_location_type == '3pl'"}
  - {key: sampling,    label: "Sampling",     sla_days: 7,  team: "Manufacturing", action: "Collect QC sample"}
  - {key: qc_ship,     label: "QCL Ship For External Testing", sla_days: 10, team: "QC Lab",        action: "Ship sample to external lab", applies_if: "offsite_test"}
  - {key: qc_testing,  label: "QCL Testing",   sla_days: 42, team: "QC Lab",        action: "Complete and approve testing"}
  - {key: qa_release,  label: "QA Release",   sla_days: 7,  team: "QA",            action: "Post usage decision"}
  - {key: released,    label: "Released",     sla_days: 0,  team: "QA",            action: "None", terminal: true}
reeval_sla_overrides:   # lot_type 09 uses these where given
  call_off: 5
  sampling: 5
  qc_testing: 27
  qa_release: 3
ud_codes:
  accept:   ["A", "A4"]
  reject:   ["R"]
  cancel:   ["X"]
metrics:  # see §7. `null_reason` is optional, and required when computed_in is app
  - {id: M1, label: "Receipt On-Time",          stage: receipt,    computed_in: app,      tier: 2, null_reason: "Physical receipt date comes from the 3PL feed, enabled in Tier 2"}
  - {id: M2, label: "Transfer On-Time",         stage: call_off,   computed_in: app,      tier: 2, null_reason: "Physical transfer date comes from the 3PL feed, enabled in Tier 2"}
  - {id: M3, label: "Sampling On-Time",         stage: sampling,   computed_in: pipeline, tier: 1}
  - {id: M4, label: "QC Ship On-Time",          stage: qc_ship,    computed_in: app,      tier: 2, null_reason: "Physical shipment date comes from the 3PL feed, enabled in Tier 2"}
  - {id: M5, label: "External Test On-Time",    stage: null, sla_days: 30, computed_in: app, tier: 2, null_reason: "External lab result date comes from the lab feed, enabled in Tier 2"}
  - {id: M6, label: "Testing On-Time",          stage: qc_testing, computed_in: pipeline, tier: 1}
  - {id: M7, label: "QA Release On-Time",       stage: qa_release, computed_in: pipeline, tier: 1}
metric_rag: {green_min_pct: 90, amber_min_pct: 80}
rag:        {amber_days_remaining_lt: 3}
air_gap:    {threshold_hours: 24}
molecule_types: [small_molecule, large_molecule, peptide]     # string or {key, label}; normalised to {key, label} (label defaults to the title-cased key)
material_classes: [drug_substance, consumable]               # same shape
full_spec_pairs: [{material: RM10031, supplier: SUP007}]   # material+supplier needing full-spec testing
terms:   # UI vocabulary (F15, OQ-075), site_a values. All keys optional; generic defaults in the note below. Code and data keep generic names
  erp: "SAP"
  lims: "LIMS"
  qms: "QMS"
  qc_lab: "QCL"
  insights_banner: "LIMS–SAP Insights"
  erp_blocked_tag: "SAP BLOCKED"
  planner_overrides: "planner overrides"
release_on_coa: {sla_days: 14}   # F18: single release deadline from cycle_start_date
exports: {sampling_plan: [sampling], qc_queue: [qc_ship, qc_testing]}   # F18: stage sets of the two queue exports
reason_codes:   # F19: labelled, shown in the Adjust Needs-by window; OTHER requires a note
  - {code: CAMPAIGN_PULLED_FORWARD, label: "Campaign pulled forward"}
  - {code: CAMPAIGN_PUSHED_BACK,    label: "Campaign pushed back"}
  - {code: VERBAL_CONFIRMATION,     label: "Verbal confirmation received"}
  - {code: SHELF_LIFE_CONSTRAINT,   label: "Shelf life constraint"}
  - {code: SUPPLIER_DELAY,          label: "Supplier/supply delay"}
  - {code: RETEST_REQUIRED,         label: "Retest required"}
  - {code: EXPEDITE_PRODUCTION,     label: "Expedite production requested"}
  - {code: EXPEDITE_SHIPPING,       label: "Expedite shipping requested"}
  - {code: TESTING_CAPACITY,        label: "Testing capacity"}
  - {code: OTHER,                   label: "Other — see notes"}
status_options:   # F19: the status log (§6)
  - {key: on_track,  label: "On Track",  colour: green}
  - {key: at_risk,   label: "At Risk",   colour: amber}
  - {key: blocked,   label: "Blocked",   colour: red}
  - {key: escalated, label: "Escalated", colour: red}
  - {key: resolved,  label: "Resolved",  colour: green}
status_reasons:   # F19: optional reason of a status entry
  - {key: process_delay,        label: "Process delay"}
  - {key: supplier_issue,       label: "Supplier issue"}
  - {key: resource_constraint,  label: "Resource constraint"}
  - {key: campaign_pull_forward, label: "Campaign pull-forward"}
  - {key: equipment_issue,      label: "Equipment issue"}
  - {key: awaiting_info,        label: "Awaiting info"}
  - {key: other,                label: "Other"}
adapters: {erp: ecc_like}       # Tier 2 adds s4_like and spreadsheet
```

**`terms` defaults** (used when a key is omitted): `erp: "ERP"`, `lims: "LIMS"`, `qms: "QMS"`, `qc_lab: "QC Lab"`, `insights_banner: "LIMS–ERP Insights"`, `erp_blocked_tag: "ERP BLOCKED"`, `planner_overrides: "planner overrides"`. Derived defaults follow `erp`/`lims`: a profile that sets only `erp: "S4"` gets "S4 BLOCKED" and "LIMS–S4 Insights".

## 3. Row grain
One published row per **material + batch + inspection lot** (ADR-004). A batch with a re-eval lot therefore appears twice: once for its historic `01` lot (typically `released`) and once for the open `09` lot. That is correct and must be displayed as such. Distinct-batch counts must aggregate on `(material_no, batch_no)`. Lots of other types are excluded at extract.

## 4. Stage engine
Inputs are the flattened row fields defined in `04-data-contracts.md` §3 (`staging.batch_flat`). Rules are **evaluated top-down and the first match wins**. Every row gets exactly one `stage_key` and the `stage_rule_id` that matched. Rules are generated from this table, and the profile can only change SLAs, labels and `applies_if`, not rule logic (Tier 1).

`resolved` inbound checks (F19) behave like `passed`: the receipt stage exits on `inbound_check_completed_date`, and R-RCP (open or failed only) does not match them.

Helper definitions (`cycle_start_date` and `ud_effective` are derived by the stage engine and **published** in `batch_pipeline_v`, so Explain shows them without recomputing; each `StageRule` lists the columns it reads in `inputs`, and every one is a published column):
- `cycle_start_date = CASE WHEN lot_type = '09' THEN lot_start_date ELSE gr_date END`. A batch whose only receipt was netted out by a same-day reversal has `gr_date = NULL` and so falls to `pending`. This is how the pending population arises
- `received_location_type`: location type of the storage location of the (netted) `101` goods receipt. It is fixed for the life of the lot. `location_type` is the *current* location and is used for display only
- `offsite_test` is always read as `COALESCE(offsite_test, false)`
- `ud_effective = ud_code IS NOT NULL AND ud_code IN accept codes`
- `ud_rejected = ud_code IN reject codes`. A rejected lot is **not** released. It stays at the stage the rules give (normally `qa_release`) with flag `ud_rejected = true`, and it is pinned as an exception
- Rows with `ud_code IN cancel codes` are **excluded** from the published pipeline (never enter the waterfall)

| Priority | Rule ID | Stage | Condition |
|---|---|---|---|
| 1 | `R-REL` | released | `ud_effective` |
| 2 | `R-QAR` | qa_release | `lims_status = 'approved' AND NOT ud_effective` |
| 3 | `R-QCT` | qc_testing | `lims_status <> 'approved' AND ((NOT offsite_test AND sample_collected_date IS NOT NULL) OR (offsite_test AND sample_shipped_date IS NOT NULL))`. Includes `lims_status = 'rejected'` (flag `lims_rejected`; retest expected) |
| 4 | `R-QCS` | qc_ship | `offsite_test AND sample_collected_date IS NOT NULL AND sample_shipped_date IS NULL` |
| 5 | `R-RCP` | receipt | `cycle_start_date IS NOT NULL AND inbound_check_status IN ('open','failed')` |
| 6 | `R-CLO` | call_off | `cycle_start_date IS NOT NULL AND received_location_type = '3pl' AND transfer_to_site_date IS NULL` |
| 7 | `R-SMP` | sampling | `cycle_start_date IS NOT NULL` (catch-all for started cycles) |
| 8 | `R-PND` | pending | otherwise |

**Stage entry/exit dates** (published per row; `NULL` if not reached):

| Stage | Entry date | Exit date |
|---|---|---|
| receipt | `cycle_start_date` | `inbound_check_completed_date` (status `passed` or `resolved`), else entry date if `inbound_check_status = 'none'` |
| call_off (3PL only) | receipt exit | `transfer_to_site_date` |
| sampling | `transfer_to_site_date` if `received_location_type='3pl'`, else receipt exit | `sample_collected_date` |
| qc_ship (offsite only) | `sample_collected_date` | `sample_shipped_date` |
| qc_testing | `sample_collected_date` (onsite) or `sample_shipped_date` (offsite) | `lims_approved_date` |
| qa_release | `lims_approved_date` | `ud_date` (when `ud_effective`) |

`current_stage_entry_date` = entry date of `stage_key`. For `pending`, it is `NULL`. `days_in_stage = today − current_stage_entry_date` (app-side, demo clock).

**Applicable stages** for a row: `receipt`, `call_off` only if `received_location_type='3pl'`, `sampling`, `qc_ship` only if `offsite_test`, `qc_testing`, `qa_release`. The **SLA per stage** = profile `sla_days`, overridden by `reeval_sla_overrides` when `lot_type='09'`. The pipeline publishes `applicable_sla_json` (ordered list of `{stage_key, sla_days}`) per row.

## 5. Plan-date maths (`r2r_core.sla`, pure functions, read-time)

### 5.1 Need-by dates
- `system_need_by_date`: earliest open MRP demand `requirement_date` for the material on or after the snapshot date. Recomputed each run (it drifts as demand moves).
- `system_need_by_locked`: the **first non-null** `system_need_by_date` ever observed for that `(material_no, batch_no, inspection_lot_no)`. It is persisted in `intelligence.need_by_history`. It locks the SLAs so they do not creep. **The pipeline publishes both**.
- `adjusted_need_by_date`: optional human override (app), held with its `reason_code`. It completely replaces the system value.
- `operative_need_by = adjusted_need_by_date ?? system_need_by_locked ?? NULL`.

### 5.2 Expected completion of the current stage (`expected_completion_date`)
Let `S` = applicable stages from the current stage (inclusive) to `qa_release`, with SLAs `sla(s)`. Let `B = Σ sla(s)` (remaining budget), `E = current_stage_entry_date`.

- **No operative need-by:** forward. `expected_completion = E + sla(current)`. Later stages chain forward (`expected(sₙ) = expected(sₙ₋₁) + sla(sₙ)`).
- **With operative need-by `N`:** available `A = N − E` (days).
  - If `A ≥ B`: no compression. Backward: `must_complete_by(s) = N − Σ sla(later applicable stages)`. `expected_completion = must_complete_by(current)`.
  - If `0 < A < B`: **proportional compression**. `ratio = A / B`. `compressed(s) = max(1, round_half_up(sla(s) × ratio))`. Then backward with compressed SLAs. Flag `compressed = true` and expose `compression_ratio`.
  - If `A ≤ 0`: `expected_completion = N − Σ compressed-to-1 later stages`. The row is already late.
- `pending` and `released` rows have no expected completion.

### 5.2b Release on COA (F18, OQ-101)
When the app override `release_on_coa` is on, the plan uses a single deadline: `expected_completion = cycle_start_date + release_on_coa.sla_days`, and `must_complete_by` of every remaining applicable stage equals that date. The need-by is ignored by the plan (still displayed, still used by §5.4), `compressed = false` and `compression_ratio = None`. `plan(..., coa_release=True)` raises `ValueError` without a `cycle_start_date`. `pending` and `released` rows cannot be set (409).

### 5.3 RAG (system, not the human status)
`days_remaining = expected_completion − today`. `red` if `days_remaining < 0`, `amber` if `0 ≤ days_remaining < profile.rag.amber_days_remaining_lt`, otherwise `green`. `late = (red)`.

### 5.4 Auto late-reason
If `late` and the row has an adjusted need-by **earlier** than `system_need_by_locked` with reason `CAMPAIGN_PULLED_FORWARD` or `EXPEDITE_*`, set `late_reason_auto = 'CAMPAIGN_PULLED_FORWARD'` (or the expedite reason), so genuine process delay is distinguishable.

### 5.5 Exceptions-first ordering (Overview table default)
1. `late` rows first (most overdue first), 2. `ud_rejected`, then `on_hold`, 3. `air_gap`, 4. remaining rows by `expected_completion` ascending (NULLs last), then `material_no`, `batch_no`.

### 5.6 Period filter
- `All dates` (default): every row not excluded.
- A period `[from, to]` shows rows where `expected_completion ≤ to` and the current stage is not terminal. Overdue rows therefore roll into every current window. Flow-strip counts are labelled **"snapshot"** under All dates and **"due in period"** otherwise.

### 5.7 Required unit-test cases (minimum)
Forward with no need-by. Backward with ample budget. Compression ratio 0.5 with rounding. `A ≤ 0`. Re-eval SLA overrides. Onsite (no call_off). Offsite (qc_ship included). Adjusted date replaces locked date. Pull-forward triggers auto reason. RAG boundaries at 0 and 3 days.

## 6. Flags (overlays, not stages)
| Flag | Source | Rule |
|---|---|---|
| `on_hold` | ERP batch status | `batch_status_code = 'H'`. The published flag stays the ERP fact. F18 adds `manual_hold` (app override) and the read-time `on_hold_display = on_hold OR manual_hold`, which drives the tag, the On Hold card, the ON HOLD filter and the sort (OQ-102). The plan maths ignores holds |
| `erp_blocked` | ERP stock | `stock_category = 'BLOCKED'` |
| `re_eval` | lot | `lot_type = '09'` |
| `offsite` | LIMS | `offsite_test` |
| `full_spec` | profile | `(material_no, supplier_id) ∈ full_spec_pairs` |
| `expedite` | app override | planner ticks EXPEDITE |
| `ud_rejected` | ERP | UD code in reject codes |
| `lims_rejected` | LIMS | `lims_status = 'rejected'` |
| `air_gap` | read-time | `lims_status='approved' AND ud_code IS NULL AND erp_results_recorded_at IS NULL AND now − lims_approved_at ≥ threshold_hours` (rejected lots are never air gaps) |

**Human status (F19).** Status and comments are one append-only **status log** (`status_log`, 04 §5), not an override: each entry has a status (profile `status_options`: On Track, At Risk, Blocked, Escalated, Resolved), a team, an optional reason and a required comment. The latest entry with a status is the row's `latest_status`. Every role except `viewer` may add an entry. The old `manual_status` overrides and `comment` rows were copied into the log by a migration (author kept, `at` = original time).

## 7. Metrics M1–M7
For metric `m` bound to stage `s`, week `w` (ISO week, Monday start, site timezone):
- `completed(w)` = rows whose exit date for `s` falls in `w`
- `on_time(w)` = those with `exit − entry ≤ sla(s, lot_type)`
- `pct = 100 × on_time / completed` (NULL if `completed = 0`)
- The pipeline publishes the last 12 complete weeks plus the current week-to-date for metrics with `computed_in: pipeline`. It also publishes the contributing rows (`weekly_metric_rows_v`), so Explain never re-implements this maths.
- For metrics with `computed_in: app`, `metric_reference_v.status = 'awaiting_signal'` with a human-readable `null_reason`. The text comes from the profile metric's `null_reason`, which is **required** when `computed_in: app` (the profile validator enforces it). Example: "Physical delivery date comes from 3PL feed, enabled in Tier 2".
- The weekly views (`weekly_metrics_v`, `weekly_metric_rows_v`) contain only `computed_in: pipeline` metrics.
- The SLA used for a row is its own entry for the stage in `applicable_sla_json` (re-evaluation and override aware). A row whose stage is not applicable is not counted.
- Weeks are ISO weeks (Monday start) in the site timezone, relative to the snapshot date: the 12 weeks before the snapshot's week, plus the snapshot's week to date. A week with no completions is still emitted, with `completed = 0` and NULL `pct`.
- The **headline value is the last complete week**. Week-to-date is shown as a secondary value, because at demo start (a Monday morning) week-to-date is empty.
- UI colour from `metric_rag`: `pct ≥ green_min_pct` green, `pct ≥ amber_min_pct` amber, otherwise red.

## 8. Quality indicators
- **Deviation light** per row: `red` if any **open** deviation is linked to the batch, `amber` if linked deviations exist and all are closed, `green` if none.
- **Inbound check light**: `red` = open or failed, `amber` = resolved (F19), `green` = passed, `grey` = none recorded.
- **Deviation severity** (F19): `minor`, `moderate`, `major`. The light does not depend on severity. Change controls linked to a batch are shown in the Quality window and never change the light.

## 9. Generic vocabulary (mandatory)
| Thing | Use | Never use |
|---|---|---|
| Company | "Demo Pharma" | any real company |
| Site | "Site A – Harbourview", "Site B – Lakeside" | real site/town names |
| Systems | "ERP", "LIMS", "QMS", "3PL" | vendor/product or client-internal platform names, **except** widely used commercial platform names (e.g. SAP) as profile `terms` values and stage labels only (05 v2 §6, OQ-075). Client-internal names never |
| Materials | `RM1xxxx` "Excipient 017", "API Intermediate 004", consumables `CN2xxxx` | real product/molecule names or codes |
| Campaigns | `CMP-ALPHA`, `CMP-BRAVO`, `CMP-CEDAR`, `CMP-DELTA`, `CMP-EMBER` | real campaign/product codes |
| Suppliers / 3PLs / labs | `SUP001`…, "3PL North", "3PL South", "External Lab A/B" | real company names |
| People | Pat (Planner), Quinn (QC), Alex (QA), Sam (Site Lead) | real people |
