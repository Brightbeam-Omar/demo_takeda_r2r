# 04 · Data Contracts

All timestamps are `timestamptz` (UTC) and all dates are `date` (site-local). Column names are `snake_case` except in the ERP simulator, which deliberately uses SAP-style short names (with friendly comments) so that ERP-literate audiences recognise the shape.

## 1. Source simulators

### 1.1 `erp_sim` (Postgres DB, "ECC-like" adapter)
| Table | Key | Columns (type · meaning) |
|---|---|---|
| `mara` | `matnr` | `matnr` text · material no · `maktx` text · description · `mtart` text · `ROH` raw / `CONS` consumable · `zmolty` text · molecule type · `zclass` text · material class · `updated_at` |
| `lfa1` | `lifnr` | `lifnr` text · supplier id (`SUP001`) · `name1` text · `land1` text · `updated_at` |
| `t001l` | `lgort` | `lgort` text · storage location (`0100`) · `lgobe` text · name · `zloctype` text · `onsite` / `3pl` |
| `mcha` | `matnr, charg` | `charg` text · batch · `lifnr` · `licha` supplier batch · `hsdat` mfg date · `vfdat` expiry · `zstat` text · `''` or `'H'` (hold) · `updated_at` |
| `mchb` | `matnr, charg, lgort` | current stock · `insme` numeric · QI qty · `speme` numeric · blocked qty · `clabs` numeric · unrestricted qty · `updated_at` |
| `mseg` | `mblnr, zeile` | `bwart` text · `101` GR, `102` GR reversal, `311` transfer · `matnr` · `charg` · `lgort` from · `umlgo` to · `budat` date posting · `updated_at` |
| `qals` | `prueflos` | `prueflos` text · inspection lot · `art` text · `01`/`09` (others excluded) · `matnr` · `charg` · `pastrterm` date start · `vcode` text · UD code · `vdatum` date · UD date · `updated_at` |
| `zinbchk` | `prueflos` | inbound check · `status` text · `open`/`passed`/`failed` · `completed_on` date · `notes` text · `updated_at` |
| `mdez` | `id` | MRP demand · `matnr` · `campaign` text · `bdter` date · requirement date · `bdmng` numeric · `is_open` bool · `updated_at` |

Rules: a GR reversal (`102`) on the same day as a `101` cancels it (the extract must net them). `mchb` holds one current location per batch in Tier 1.

### 1.2 `lims_sim`
| Table | Key | Columns |
|---|---|---|
| `sample` | `sample_id` | `inspection_lot_no`, `material_no`, `batch_no`, `collected_date` date, `offsite_test` bool, `external_lab` text null, `shipped_date` date null, `status` text (`registered`,`in_progress`,`approved`,`rejected`), `approved_at` timestamptz null, `updated_at` |
| `test_result` | `id` | `sample_id`, `test_code`, `test_name`, `result_value` text, `spec` text, `status` (`pending`,`pass`,`fail`,`oos`), `completed_at`, `updated_at` (used by Tier 2 release-readiness) |

The REST API (`lims-sim`) exposes `GET /samples?batch_no=` and `GET /samples/{id}/results` for agents. The pipeline reads the DB directly.

### 1.3 `qms_sim`
| Table | Key | Columns |
|---|---|---|
| `deviation` | `deviation_no` | `title`, `description`, `severity` (`minor`,`major`,`critical`), `status` (`open`,`closed`), `opened_on`, `closed_on`, `root_cause_category`, `owner`, `updated_at` |
| `deviation_link` | `deviation_no, material_no, batch_no` | links a deviation to batches |
| `capa`, `change_control` | n/a | Tier 2 |

## 2. Lakehouse layout (`./lakehouse`, Delta)
```
lakehouse/
  staging/        stg_mara, stg_lfa1, stg_t001l, stg_mcha, stg_mchb, stg_mseg, stg_qals, stg_zinbchk,
                  stg_mdez, stg_sample, stg_deviation, stg_deviation_link, batch_flat     (overwrite per run)
  intelligence/   batch_snapshot (append/replace by snapshot_date), weekly_metrics, need_by_history,
                  pipeline_run_log
  published/      batch_pipeline_v, weekly_metrics_v, weekly_metric_rows_v, pipeline_status_v,
                  stage_reference_v, metric_reference_v, reason_codes_v, deviations_v  (overwrite per run)
```
Even though the published tables are suffixed `_v`, they are materialised Delta tables, not views.

## 3. `staging.batch_flat` (input to the stage engine)
One row per `material_no, batch_no, inspection_lot_no` for lot types `01`/`09`, excluding cancelled UDs.

`material_no, material_desc, material_class, molecule_type, supplier_id, supplier_name, supplier_batch, batch_no, batch_status_code, inspection_lot_no, lot_type, lot_start_date, storage_location, location_type, received_location_type, stock_category, gr_date, transfer_to_site_date, inbound_check_status ('none' if absent), inbound_check_completed_date, sample_id, sample_collected_date, offsite_test, external_lab, sample_shipped_date, lims_status ('none' if no sample), lims_approved_date, lims_approved_at, ud_code, ud_date, campaign, system_need_by_date, open_deviation_count, closed_deviation_count, source_refs_json`

Derivations (non-obvious columns):

| Column | Derivation |
|---|---|
| `gr_date` | `MIN(mseg.budat)` of `bwart='101'` for the batch **after** removing 101s that have a same-day `102` for the same batch and quantity |
| `received_location_type` | `t001l.zloctype` of `mseg.lgort` on that netted `101` |
| `transfer_to_site_date` | `MIN(mseg.budat)` of `bwart='311'` where `t001l(umlgo).zloctype='onsite'` and `budat ≥ gr_date` |
| `storage_location`, `location_type` | From `mchb` with the largest total qty for the batch. If there is no stock (consumed/released), the last `mseg` destination |
| `stock_category` | `BLOCKED` if `speme > 0`, else `QI` if `insme > 0`, else `UNRESTRICTED` |
| `lot_start_date` | `qals.pastrterm` |
| `inbound_check_status` | `zinbchk.status` for the lot, else `'none'` |
| `lims_status` | Latest `sample.status` for the lot: `registered`/`in_progress` → `in_progress`, `approved`, `rejected`. `'none'` if there is no sample |
| `lims_approved_date` | `lims_approved_at` converted to the site timezone (profile) and truncated to date |
| `system_need_by_date`, `campaign` | From the single `mdez` row chosen as the earliest open `bdter ≥ snapshot_date` for the material (tie-break: lowest `id`). `campaign` is that row's campaign |
| `open_/closed_deviation_count` | Via `deviation_link` on `(material_no, batch_no)` |

`source_refs_json` example: `{"erp":{"mcha":"RM10023|B1042","qals":"10000042","mseg":["4900001234"]},"lims":{"sample":"S-77812"},"qms":{"deviation":["DEV-000123"]}}`

## 4. Published contract (what the app mirrors)

### 4.1 `batch_pipeline_v`
`row_key` (`material_no|batch_no|inspection_lot_no`), every `batch_flat` business column, plus:
`stage_key, stage_rule_id, stage_sort, current_stage_entry_date, lims_rejected, receipt_entry, receipt_exit, call_off_entry, call_off_exit, sampling_entry, sampling_exit, qc_ship_entry, qc_ship_exit, qc_testing_entry, qc_testing_exit, qa_release_entry, qa_release_exit, applicable_sla_json, system_need_by_locked, on_hold, erp_blocked, re_eval, offsite, full_spec, ud_rejected, deviation_light, inbound_light, snapshot_date, run_id, published_at`

### 4.2 `weekly_metrics_v`
`metric_id, week_start (date), completed (int), on_time (int), pct (decimal 5,1 null), run_id`

### 4.2b `weekly_metric_rows_v`
`metric_id, week_start, row_key, entry_date, exit_date, duration_days, sla_days, on_time (bool), run_id`. These are the contributing rows behind every `weekly_metrics_v` figure

### 4.3 `pipeline_status_v` (exactly one row: last successful run)
`last_run_id` (= the Dagster run id), `started_at, last_success_at, row_count, source_freshness_json` (`{"erp":{"max_updated_at":…, "extracted_at":…},"lims":{…},"qms":{…}}`). Failed runs are recorded in `intelligence.pipeline_run_log` but are not published.

### 4.4 Reference objects (built from the site profile)
- `stage_reference_v`: `stage_key, label, sort, sla_days, reeval_sla_days, team, action, terminal`
- `metric_reference_v`: `metric_id, label, stage_key, sla_days, computed_in, status ('active'|'awaiting_signal'), null_reason`
- `reason_codes_v`: `code, label`

### 4.5 `deviations_v`
`deviation_no, material_no, batch_no, title, severity, status, opened_on, closed_on, root_cause_category, owner`

## 5. Application database (`app`)
| Table | Purpose / key columns |
|---|---|
| `app_user` | `user_key` PK, `display_name`, `role` (`planner`,`qc_lead`,`qa_release`,`viewer`,`admin`). Seed: `pat`/Pat/planner, `quinn`/Quinn/qc_lead, `alex`/Alex/qa_release, `sam`/Sam/viewer, `admin`/Admin/admin |
| `demo_clock` | `id=1`, `now_utc`, `frozen`. **Owned by F04** (first app migration). The clock moves only via set/advance |
| `sync_event` | `id` PK, `source` (`webhook`,`poll`,`manual`), `run_id`, `status` (`pending`,`claimed`,`done`,`failed`), `received_at`, `claimed_at`, `finished_at`, `error`, `rows_upserted` |
| `watermark` | `object_name` PK, `run_id`, `synced_at` |
| `mirror_batch_pipeline`, `mirror_weekly_metrics`, `mirror_weekly_metric_rows`, `mirror_pipeline_status`, `mirror_stage_reference`, `mirror_metric_reference`, `mirror_reason_codes`, `mirror_deviations` | Same columns as the published object, plus `contract_run_id`, `mirrored_at`. Replaced wholesale per sync in one transaction |
| `override_value` | `id`, `row_key`, `field` (`adjusted_need_by_date`,`expedite`,`manual_status`,`delivery_date`,`delivery_location`), `value_json`, `reason_code` null, `note` null, `version` int, `author_user_key`, `created_at`, `is_current` bool. Unique partial index on `(row_key, field) WHERE is_current`. **Insert-only**: a new version sets the prior row's `is_current=false` in the same transaction. A "clear" is a new version with `value_json = null` |
| `comment` | `id`, `row_key`, `body`, `author_user_key`, `created_at` (insert-only) |
| `audit_event` | `id`, `at`, `actor_user_key`, `action`, `row_key` null, `details_json`. Written for every override, comment, approval, rejection and agent action |
| `proposal` | `id`, `agent_key`, `row_key` null, `kind` (e.g. `airgap_ticket`), `payload_json`, `evidence_json`, `validator_result_json`, `status` (`pending_approval`,`rejected_by_validator`,`approved`,`rejected`,`executed`), `required_role`, `created_at`, `decided_by`, `decided_at`, `trace_id` |
| `action_log` | `id`, `proposal_id`, `action_type`, `rendered_json`, `executed_at` |
| `agent_trace` | `id`, `trace_id`, `seq`, `step_type` (`input`,`tool_call`,`tool_result`,`model_request`,`model_response`,`validation`,`decision`,`action`), `payload_json`, `tokens_in`, `tokens_out`, `latency_ms`, `at` |

Override fields are composed at read time: `operative = current override value ?? mirror value`.
