# 04 · Data Contracts

All timestamps are `timestamptz` (UTC) and all dates are `date` (site-local). Column names are `snake_case` except in the ERP simulator, which deliberately uses SAP-style short names (with friendly comments) so that ERP-literate audiences recognise the shape.

## 1. Source simulators

### 1.1 `erp_sim` (Postgres DB, "ECC-like" adapter)
| Table | Key | Columns (type · meaning) |
|---|---|---|
| `mara` | `matnr` | `matnr` text · material no · `maktx` text · description · `mtart` text · `ROH` raw / `CONS` consumable · `zmolty` text · molecule type · `zclass` text · material class · `updated_at` |
| `lfa1` | `lifnr` | `lifnr` text · supplier id (`SUP001`) · `name1` text · `land1` text · `updated_at` |
| `t001l` | `lgort` | `lgort` text · storage location (`0100`) · `lgobe` text · name · `zloctype` text · `onsite` / `3pl` |
| `mcha` | `matnr, charg` | `charg` text · batch · `lifnr` · `licha` supplier batch · `hsdat` mfg date · `vfdat` expiry · `zstat` text · `''` or `'H'` (hold) · `qnext` date null · next inspection (retest) date, F18, OQ-100 · `updated_at` |
| `mchb` | `matnr, charg, lgort` | current stock · `insme` numeric · QI qty · `speme` numeric · blocked qty · `clabs` numeric · unrestricted qty · `updated_at` |
| `mseg` | `mblnr, zeile` | `bwart` text · `101` GR, `102` GR reversal, `311` transfer · `matnr` · `charg` · `lgort` · `umlgo` · `budat` date posting · `menge` numeric(13,3) quantity · `ebeln`, `ebelp` text null · the PO line a `101` closed (F17, OQ-092) · `updated_at`. For `101`/`102`, `lgort` is the **receiving storage location** and `umlgo` is null. For `311`, `lgort` is the **source** and `umlgo` the **destination** |
| `qals` | `prueflos` | `prueflos` text · inspection lot · `art` text · `01`/`09` (others excluded) · `matnr` · `charg` · `pastrterm` date start · `vcode` text · UD code · `vdatum` date · UD date · `zresrec` timestamptz null · LIMS results recorded in ERP via interface (set by the `results-recorded` event; a usage decision does not set it) · `updated_at` |
| `zinbchk` | `prueflos` | inbound check · `status` text · `open`/`passed`/`failed` · `completed_on` date · `notes` text · `updated_at` |
| `ekpo` | `ebeln, ebelp` | open purchase-order lines, a pre-batch grain (F17) · `ebeln` text · PO number, 10 digits starting `45` · `ebelp` text · line, `00010` in steps of 10 · `matnr` · `lifnr` · `eindt` date · scheduled delivery · `menge` numeric(13,3) · `lgort` · planned receiving location · `is_open` bool · `updated_at`. A `101` that carries `ebeln/ebelp` closes the line; a `102` reopens the line of the `101` it nets; a GR with no PO reference reopens nothing |
| `mdez` | `id` | MRP demand · `matnr` · `campaign` text · `bdter` date · requirement date · `bdmng` numeric · `is_open` bool · `updated_at` |

Rules: a GR reversal (`102`) on the same day as a `101` for the same batch and quantity (`menge`) cancels it (the extract must net them). `mchb` holds one current location per batch in Tier 1.

**Conventions (F04).**
- **`updated_at`:** every table in the three simulators has `updated_at timestamptz not null`, indexed, stamped by service code from `r2r_core.clock.now()` on every insert and update (never by a DB trigger). That includes `deviation_link` and the helper table `counter`. `app.demo_clock` is the only exception (it is the clock).
- **Types:** quantities are `numeric(13,3)`; keys and codes are `text`; dates are `date`. The simulators' JSON APIs return `numeric` values as **strings** (`"100.000"`) so no precision is lost; the pipeline reads the databases directly.
- **Foreign keys:** `mcha`→`mara`, `lfa1`; `mchb`→`mcha`, `t001l`; `mseg`→`mcha`, `t001l` (`lgort`, and `umlgo` when set); `qals`→`mcha`; `zinbchk`→`qals`; `mdez`→`mara`. `lims_sim.sample` has no FK (it refers to the ERP lot by number, across databases). `test_result`→`sample`; `deviation_link`→`deviation`.
- **Indexes:** `updated_at` on every table, and `(matnr, charg)` / `(material_no, batch_no)` wherever those columns exist.
- **Number formats** (allocated from per-database counters, so a reset restarts numbering): material document `mblnr` is 10 digits starting `49` (for example `4900001234`) with `zeile` `0001` (one line per document in Tier 1); inspection lot `prueflos` is 8 digits starting `1` (for example `10000042`); `mdez.id` is an integer; sample id `S-0000001`; deviation `DEV-000001`.
- **Stock buckets (`mchb`)** per batch and storage location: `insme` quality inspection (QI), `speme` blocked, `clabs` unrestricted. A `101` puts the quantity in QI. A `102` takes it out of QI. A `311` moves the quantity to the destination location in the same buckets; the source row is deleted when it is empty. A usage decision `accept` moves QI to unrestricted, `reject` moves QI to blocked (so `erp_blocked` is also true for rejected lots), `cancel` leaves stock unchanged. `stock-block` / `stock-unblock` move quantity between QI and blocked without a usage decision.
- **Lots:** the initial lot (`01`) is opened by the goods receipt together with an `open` inbound check. A re-evaluation lot (`09`) is opened on an existing batch by `reeval-lot`; its inbound check row exists only if the event asks for one. A goods receipt that is fully reversed leaves the batch, lot and check rows in place; the pipeline derives the `pending` stage from the netted receipt.

### 1.2 `lims_sim`
| Table | Key | Columns |
|---|---|---|
| `sample` | `sample_id` | `inspection_lot_no`, `material_no`, `batch_no`, `collected_date` date, `offsite_test` bool, `external_lab` text null, `shipped_date` date null, `status` text (`registered`,`in_progress`,`approved`,`rejected`), `approved_at` timestamptz null, `updated_at` |
| `test_result` | `id` | `sample_id`, `test_code`, `test_name`, `result_value` text, `spec` text, `status` (`pending`,`pass`,`fail`,`oos`), `completed_at`, `updated_at` (used by Tier 2 release-readiness) |

Sample ids are counter-allocated and zero-padded (`S-0000001`). A rejected sample is retested by a **new** sample for the same lot, so the **latest sample for a lot is the one with the maximum `sample_id`**. `test_result` is created empty in F04: the `approved` and `rejected` events do not write results (the generator may seed them; Tier 2 uses them). `sample` has `updated_at` as every table does.

The REST API (`lims-sim`) exposes `GET /samples?batch_no=` and `GET /samples/{id}/results` for agents. The pipeline reads the DB directly.

### 1.3 `qms_sim`
| Table | Key | Columns |
|---|---|---|
| `deviation` | `deviation_no` | `title`, `description`, `severity` (`minor`,`major`,`critical`), `status` (`open`,`closed`), `opened_on`, `closed_on`, `root_cause_category`, `owner`, `updated_at` |
| `deviation_link` | `deviation_no, material_no, batch_no` | links a deviation to batches · `updated_at` |
| `capa`, `change_control` | n/a | Tier 2 |

`deviation_no` is `DEV-000001`-style (counter-allocated). `root_cause_category` is free text from a short generic list used by the generator and `owner` is a role name such as `QA`; neither list is enforced.

## 2. Lakehouse layout (`./lakehouse`, Delta)
```
lakehouse/
  staging/        stg_mara, stg_lfa1, stg_t001l, stg_mcha, stg_mchb, stg_mseg, stg_qals, stg_zinbchk,
                  stg_mdez, stg_ekpo, stg_sample, stg_deviation, stg_deviation_link, batch_flat, batch_stage   (overwrite per run)
  intelligence/   batch_snapshot (append/replace by snapshot_date), weekly_metrics, weekly_metric_rows, need_by_history,
                  pipeline_run_log
  published/      batch_pipeline_v, weekly_metrics_v, weekly_metric_rows_v, pipeline_status_v,
                  stage_reference_v, metric_reference_v, reason_codes_v, deviations_v, expected_deliveries_v  (overwrite per run)
```
Even though the published tables are suffixed `_v`, they are materialised Delta tables, not views.

### 2.1 Intelligence tables (F07)
| Table | Columns |
|---|---|
| `batch_snapshot` | `staging.batch_flat` joined to `staging.batch_stage` on `row_key` (every column of both), plus `snapshot_date`, `run_id`, `system_need_by_locked`. Partitioned by `snapshot_date`; a run replaces only its own date's partition |
| `need_by_history` | `row_key`, `system_need_by_date`, `first_seen_date`, `run_id`. Holds the **first non-null** `system_need_by_date` per `row_key`; rows are only inserted, never updated. `system_need_by_locked` = this value, else NULL (a row released before it ever had demand stays NULL) |
| `weekly_metrics` | the `weekly_metrics_v` columns (`metric_id, week_start, completed, on_time, pct`) plus `run_id`. Only metrics with `computed_in: pipeline`; the last 12 complete ISO weeks plus the current week to date, relative to the snapshot date; empty weeks have `completed = 0` and NULL `pct`. Replaced wholesale each run |
| `weekly_metric_rows` | the `weekly_metric_rows_v` columns (`metric_id, week_start, row_key, entry_date, exit_date, duration_days, sla_days, on_time`) plus `run_id`: the rows behind every `weekly_metrics` figure. Replaced wholesale each run |
| `pipeline_run_log` | `run_id, step, status ('success'/'failed'), started_at, finished_at, rows, error, notify_status ('ok'/'failed'/'skipped', notify row only), detail_json`. One row per step per run, appended. `detail_json` carries step details (the `extract` row holds the per-source freshness that `publish` reads for `source_freshness_json`) |

Run order and publishing: the published objects are written one by one in the order of §4 (`batch_pipeline_v`, `weekly_metrics_v`, `weekly_metric_rows_v`, `stage_reference_v`, `metric_reference_v`, `reason_codes_v`, `deviations_v`, `expected_deliveries_v`) with `pipeline_status_v` **last**. Every object except the reference ones carries the `run_id`, so a reader can detect a mixed state after a crash inside `publish`.

## 3. `staging.batch_flat` (input to the stage engine)
One row per `material_no, batch_no, inspection_lot_no` for lot types `01`/`09`, excluding cancelled UDs.

`material_no, material_desc, material_class, molecule_type, supplier_id, supplier_name, supplier_batch, batch_no, batch_status_code, inspection_lot_no, lot_type, lot_start_date, storage_location, location_type, received_location_type, stock_category, gr_date, transfer_to_site_date, inbound_check_status ('none' if absent), inbound_check_completed_date, sample_id, sample_collected_date, offsite_test, external_lab, sample_shipped_date, lims_status ('none' if no sample), lims_approved_date, lims_approved_at, ud_code, ud_date, erp_results_recorded_at, campaign, system_need_by_date, open_deviation_count, closed_deviation_count, next_inspection_date` (F18: `mcha.qnext` of the batch, NULL when none)

Derivations (non-obvious columns):

| Column | Derivation |
|---|---|
| `gr_date` | `MIN(mseg.budat)` of `bwart='101'` for the batch **after** netting: a `102` cancels at most one `101` of the same batch, posting date and quantity, and each `101` is cancelled at most once. Unmatched or partial reversals stay as posted. `stg_mseg` is a raw copy; netting happens here |
| `received_location_type` | `t001l.zloctype` of `mseg.lgort` on that netted `101`. For `lot_type = '09'` it is always `onsite` (a re-evaluation cycle starts with the stock on site) |
| `transfer_to_site_date` | `MIN(mseg.budat)` of `bwart='311'` where `t001l(umlgo).zloctype='onsite'` and `budat ≥ gr_date` |
| `storage_location`, `location_type` | From `mchb` with the largest total qty for the batch; ties go to the lowest location number. If there is no stock (consumed/released), the last `mseg` destination |
| `stock_category` | From the bucket sums over all the batch's `mchb` rows: `BLOCKED` if the sum of `speme > 0`, else `QI` if the sum of `insme > 0`, else `UNRESTRICTED` |
| `inbound_check_completed_date` | `zinbchk.completed_on` only when the status is `passed`; NULL for `open`, `failed` or no check (so a failed check leaves the receipt stage without an exit date) |
| `lot_start_date` | `qals.pastrterm` |
| `inbound_check_status` | `zinbchk.status` for the lot, else `'none'` |
| `lims_status` | Latest `sample.status` for the lot: `registered`/`in_progress` → `in_progress`, `approved`, `rejected`. `'none'` if there is no sample |
| `erp_results_recorded_at` | `qals.zresrec` for the lot (NULL if never recorded) |
| `lims_approved_date` | `lims_approved_at` converted to the site timezone (profile) and truncated to date |
| `system_need_by_date`, `campaign` | From the single `mdez` row chosen as the earliest open `bdter ≥ snapshot_date` for the material (tie-break: lowest `id`). `campaign` is that row's campaign. Joined to rows whose `ud_code` is not an accept code of the profile; released rows get NULL |
| `open_/closed_deviation_count` | Via `deviation_link` on `(material_no, batch_no)` |

### 3b. `staging.batch_stage` (output of the stage engine)
One row per `row_key`, built by the SQL steps `50`–`90` from `batch_flat`: `row_key` plus the columns of §4.1 from `stage_key` to `inbound_light` (stage, rule id, the two derived rule inputs `cycle_start_date` and `ud_effective`, sort, entry and exit dates per stage, flags, lights, `applicable_sla_json`, `source_refs_json`). `snapshot_date`, `run_id`, `published_at` and `system_need_by_locked` are added by F07, which joins `batch_flat` and `batch_stage` to publish `batch_pipeline_v`.

`source_refs_json` lists every material document of the batch (netted ones included), ordered by number. Example: `{"erp":{"mcha":"RM10023|B1042","qals":"10000042","mseg":["4900001234"]},"lims":{"sample":"S-77812"},"qms":{"deviation":["DEV-000123"]}}`

## 4. Published contract (what the app mirrors)

### 4.1 `batch_pipeline_v`
`row_key` (`material_no|batch_no|inspection_lot_no`), every `batch_flat` business column (including `erp_results_recorded_at`), plus:
`stage_key, stage_rule_id, cycle_start_date, ud_effective, stage_sort, current_stage_entry_date, lims_rejected, receipt_entry, receipt_exit, call_off_entry, call_off_exit, sampling_entry, sampling_exit, qc_ship_entry, qc_ship_exit, qc_testing_entry, qc_testing_exit, qa_release_entry, qa_release_exit, applicable_sla_json, source_refs_json, system_need_by_locked, next_inspection_date, on_hold, erp_blocked, re_eval, offsite, full_spec, ud_rejected, deviation_light, inbound_light, snapshot_date, run_id, published_at`

### 4.2 `weekly_metrics_v`
`metric_id, week_start (date), completed (int), on_time (int), pct (decimal 5,1 null), run_id`

### 4.2b `weekly_metric_rows_v`
`metric_id, week_start, row_key, entry_date, exit_date, duration_days, sla_days, on_time (bool), run_id`. These are the contributing rows behind every `weekly_metrics_v` figure

### 4.3 `pipeline_status_v` (exactly one row: last successful run)
`last_run_id` (= the Dagster run id), `started_at, last_success_at, row_count, source_freshness_json` (`{"erp":{"max_updated_at":…, "extracted_at":…},"lims":{…},"qms":{…}}`). Failed runs are recorded in `intelligence.pipeline_run_log` but are not published.

### 4.4 Reference objects (built from the site profile)
- `stage_reference_v`: `stage_key, label, sort, sla_days, reeval_sla_days, team, action, terminal, show_card` (F17)
- `metric_reference_v`: `metric_id, label, stage_key, sla_days, computed_in, status ('active'|'awaiting_signal'), null_reason`
- `reason_codes_v`: `code, label`

### 4.6 `expected_deliveries_v` (F17)
`ebeln, ebelp, material_no, material_desc, molecule_type, material_class, supplier_id, supplier_name, campaign, scheduled_date, quantity, planned_location, planned_location_type, overdue (bool, `scheduled_date` < snapshot date), run_id`. One row per open PO line. `campaign` is the material's earliest open demand campaign (as for batch rows).

### 4.5 `deviations_v`
`deviation_no, material_no, batch_no, title, severity, status, opened_on, closed_on, root_cause_category, owner`

## 5. Application database (`app`)
| Table | Purpose / key columns |
|---|---|
| `app_user` | `user_key` PK, `display_name`, `role` (`planner`,`qc_lead`,`qa_release`,`viewer`,`admin`). Seed: `pat`/Pat/planner, `quinn`/Quinn/qc_lead, `alex`/Alex/qa_release, `sam`/Sam/viewer, `admin`/Admin/admin |
| `demo_clock` | `id` int primary key with `CHECK (id = 1)`, `now_utc timestamptz not null`, `frozen boolean not null default false`. **Owned by F04** (first app migration, `0001_demo_clock`, in the `app_api` package). No `updated_at` (it is the clock). The `scenario` service inserts the row on first start from the profile's `demo.start_datetime` and never overwrites it. The clock moves only via set/advance |
| `sync_event` | `id` PK, `source` (`webhook`,`poll`,`manual`), `run_id` (informational; null for manual), `status` (`pending`,`claimed`,`done`,`failed`), `received_at`, `claimed_at`, `finished_at`, `error`, `rows_upserted`. Times are infrastructure time (Postgres `now()`), not the demo clock; the API exposes them as ISO timestamps plus `age_seconds` and `duration_ms` |
| `watermark` | `object_name` PK, `run_id`, `synced_at`. One row per mirrored object (nine rows). Reference objects, which carry no `run_id`, take the pipeline's `last_run_id`. `synced_at` is infrastructure time (Postgres `now()`) |
| `mirror_batch_pipeline`, `mirror_weekly_metrics`, `mirror_weekly_metric_rows`, `mirror_pipeline_status`, `mirror_stage_reference`, `mirror_metric_reference`, `mirror_reason_codes`, `mirror_deviations`, `mirror_expected_deliveries` (F17; primary key `(ebeln, ebelp)`) | Same columns as the published object, plus `contract_run_id`, `mirrored_at`. Replaced wholesale per sync in one transaction (`DELETE` then insert, so readers never block). Native types (`date`, `timestamptz`, `numeric`, `boolean`, `text`); `applicable_sla_json`, `source_refs_json` and `source_freshness_json` are `jsonb`. Primary keys: `row_key` (batch pipeline); `(metric_id, week_start)` (weekly metrics); `(metric_id, week_start, row_key)` (metric rows); one row (status); `stage_key`; `metric_id`; `code`; `(deviation_no, material_no, batch_no)`. Indexes on `stage_key` and `(material_no, batch_no)` for `mirror_batch_pipeline` |
| `override_value` | `id`, `row_key`, `field` (`adjusted_need_by_date`,`expedite`,`manual_status`,`delivery_date`,`delivery_location`,`manual_hold`,`release_on_coa`; the last two carry `{"on": bool, "reason": str}` with a 3–200 character reason, F18, OQ-103), `value_json`, `reason_code` null, `note` null, `version` int, `author_user_key`, `created_at`, `is_current` bool. Unique partial index on `(row_key, field) WHERE is_current`. **Insert-only**: a new version sets the prior row's `is_current=false` in the same transaction. A "clear" is a new version with `value_json = null` |
| `comment` | `id`, `row_key`, `body`, `author_user_key`, `created_at` (insert-only) |
| `audit_event` | `id`, `at` (demo clock), `actor_user_key` (nullable text; `system` for system rows such as a rejected webhook), `action`, `row_key` null, `details_json`. Written for every override, comment, approval, rejection and agent action |
| `feedback` | `id`, `at` (demo clock), `user_key`, `page` (route path, ≤ 200 chars), `message` (1–2000 chars). Insert-only, not audited (F15, OQ-083) |
| `bookmark` | `user_key`, `row_key`, `created_at` (demo clock). PK (`user_key`, `row_key`). Personal, not audited (F16, OQ-091) |
| `filter_preset` | `id`, `user_key`, `name`, `query` (the filter query string, `period` stored literally), `created_at` (demo clock). Unique (`user_key`, `name`). Not audited (F16, OQ-089) |
| `proposal` | `id`, `agent_key`, `row_key` null, `kind` (e.g. `airgap_ticket`), `payload_json`, `evidence_json`, `validator_result_json`, `status` (`pending_approval`,`rejected_by_validator`,`approved`,`rejected`,`executed`), `required_role`, `created_at`, `decided_by`, `decided_at`, `trace_id` |
| `action_log` | `id`, `proposal_id`, `action_type`, `rendered_json`, `executed_at` |
| `agent_trace` | `id`, `trace_id`, `seq`, `step_type` (`input`,`tool_call`,`tool_result`,`model_request`,`model_response`,`validation`,`decision`,`action`), `payload_json`, `tokens_in`, `tokens_out`, `latency_ms`, `at` |

Override fields are composed at read time: `operative = current override value ?? mirror value`.
