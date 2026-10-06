# F19 · Batch Drawer and Windows: History, Inbound, Quality, Status Log, Sample Data, Adjust Needs-by

## Context
The as-built dashboard opens a **focused window per cell**. This feature keeps F11's **batch drawer as the batch's home** and adds five modal windows (05 v2 §5) for the per-cell parity, plus the source data they need: inbound sub-checks, change controls, richer deviations, published samples, and a status log. *(Design change, OQ-116: the drawer is kept and made non-modal; W1 Batch History is no longer a window, its content is the drawer's top sections.)*

**F11 reuse:** keep the F11 backend (preview endpoint, audit filters, explain) and the Explain popovers. The drawer components in `components/drawer/*` are **refactored into the new sections, not deleted**. `/overview?row=<row_key>` opens the drawer.

## Batch drawer (the batch's home; replaces W1 Batch History)
Non-modal, 560 px, right side. The table stays interactive behind it: clicking another row swaps the drawer's content, and the persona switcher works while it is open (the F11 "close the drawer before switching persona" limitation is removed). It opens from the batch link, a row click, Enter, and `?row=<row_key>`. It loads from `/api/rows/{row_key}` independently of the table (OQ-072). The header keeps the F11 content (material, batch, lot, stage chip, tags).

**History sections (the former W1), in this order. Values in the sketch are illustrative**
```
B4410 · Excipient 021 · lot 09                                       ×
┌ MATERIAL            CURRENT STAGE   ┐
│ Excipient 021       SAMPLING        │
│ TOTAL DAYS          NEXT INSPECTION │
│ 4d / 45d target     <date>          │
└─────────────────────────────────────┘
[RE-EVAL]
MILESTONE DATES
 Goods Receipt: <parent GR>     Call-Off Target: —
 First Sampled: (pending)       Sample Shipped: —
 Usage Decision: (pending)
STAGE TIMELINE
 ● Receipt      Entered 08 Oct 2026  Exited 08 Oct 2026 · SLA: 10d          0d
 ● Sampling     Entered 08 Oct 2026  In progress · SLA: 5d                  4d   (blue = current)
OTHER LOTS OF THIS BATCH
 Initial (01) Released … · Re-eval 1 (09) Released … · Re-eval 2 … · Re-eval 3 … · Re-eval 4 (current) …
[↓ Export]
```
- **Summary:** material, current stage, **Total Days** = today − cycle start against target = Σ applicable SLAs (green within, red over), next inspection date, tags.
- **Milestones:** goods receipt, call-off target (cycle start + receipt SLA, 3PL rows only), first sampled, sample shipped, usage decision. Each shows the gap "+Nd from <previous>". Missing ones show *(pending)*.
- **Timeline:** one entry per stage reached, with entered/exited dates, SLA and days. The dot is green if within SLA, red if over (with "+Nd over" and red days), and blue for the current stage ("In progress").
- **Other lots:** all lots of the same batch, oldest first, the current one marked "current" (B4410 has 5 lots: Initial, Re-eval 1–3 and the current re-eval, F11 AC-03 kept). Each other lot opens its own drawer content.
- Footnote: "Derived from pipeline facts; a stage entered and left on the same day shows 0d."
- **Export** CSV of the timeline. Closing the drawer puts the batch number into the table's Batch filter box (parity).

**Summary sections below the history.** Each is a short summary with an "Open ↗" link to its window. The windows also open directly from the table cells, as in the real product.

| Section | Shows | Opens |
|---|---|---|
| Quality | RAG, open deviations count, change count | W3 |
| Inbound | Result, failed-check count | W2 |
| Status log | Latest entry, history count | W4 (add an update there) |
| Samples | Count per status | W5 |
| Need-by | System and adjusted dates, reason, Set By | W6 |
| Source refs | Collapsed, unchanged from F11 | n/a |

## Windows (modal; W1 is the drawer above)
### W2 Inbound (inbound dot)
- **Header:** a status block with a dot and result (**Passed** green / **Completed (Resolved)** amber / **Failed** or **Open** red / **No status** grey), plus the material.
- **INBOUND CHECK** section: `<terms.erp>` lot number, check deadline (cycle start + receipt SLA), and **Failed checks: n** when n > 0.
- **SUB-CHECKS:** a list of label → outcome code (PASS, FAIL in red, Pending, NO, COMP, APRV, DCPS).
- **CHECK RESULTS:** the overall verdict.
- Grey state: "No inbound check recorded."

### W3 Quality (deviation dot)
- **Header:** the RAG rating with "n open deviation(s)", plus the material(s).
- **Tabs, each with a count:** Open Deviations · Closed / Cancelled · Changes.
- **Controls:** severity pills ALL / Major / Moderate / Minor, a sort ("Newest first" or "Oldest first"), and expand-all / collapse-all.
- **Deviation card:**
  - **Top line:** `Ref: DEV-000123`, severity badge, status badge, date raised.
  - **Body:** title, Causal Factor, Root Cause, Description, and Investigation Summary (when present).
- **Change card:** reference, status, title, current → proposed description, and the effective date.
- A green rating can still show Changes (parity note).

### W4 Status Log (speech-bubble icon in Status)
- **Header:** material · stage, with **Latest** and **History (n)** tabs (History only when n > 1).
- **Entry:** a status dot (colour of the chosen status), area/team, author, demo timestamp, reason (italic) and comment. History is newest first, with a sort toggle.
- **Form:**
  - **Status** (profile `status_options`; site_a: On Track green, At Risk amber, Blocked red, Escalated red, Resolved green).
  - **Area / Team** (from the stage reference teams).
  - **Reason**, optional, from profile `status_reasons`: Process delay, Supplier issue, Resource constraint, Campaign pull-forward, Equipment issue, Awaiting info, Other.
  - **Comment**, required.
  - `Add Status Update` stays disabled until there is a comment. `Close`.
- Roles: everyone except viewer may add (**record an OQ that supersedes OQ-071**, which restricted status to qc_lead/qa_release/admin; the log now carries comments too).
- **This replaces F09/F11 "manual status" and "comments" as one append-only log.** The latest entry's status and comment show beneath the Status cell (F18).

### W5 Sample Data (sample-count badge)
- Title "Sample Data — B1042 (n samples)", with the explanatory line "`<terms.lims>` sample records for this batch. Click a Sample ID to copy it."
- Filter pills: All (n) / Received (n) / Approved (n), plus Rejected (n) when any.
- `DataTable` with Sample ID (click to copy, toast "Copied") and Status chip, plus Collected and Approved dates as demo additions.

### W6 Adjust Needs-by Date (Adjusted Date cell)
```
Adjust Needs-by Date — B2077                                                 ×
┌ Material              Excipient 017 ┐
│ System Needs-by        03 Dec 2026  │
└─────────────────────────────────────┘
New Adjusted Date [26 Nov 2026 📅]
−7d (pulled forward)                        (red; "+3d (pushed back)" green)
Reason for Change * [— Select a reason — ▾]
☐ Expedite — tag this batch as expedited (tracked as a separate metric)
Compressed stage deadlines (preview) — every remaining stage's SLA budget is compressed proportionally
 • Sampling: 14 Oct 2026   • QCL Testing: 20 Nov 2026   • QA Release: 26 Nov 2026
 Estimates for sense-checking; the scheduled pipeline run remains authoritative.
Notes (optional)  [                         ]
[Cancel]  [Save] (disabled until a reason is chosen; "Other — see notes" requires notes)
[Clear override] (when one exists)
```
- **Reason list (profile `reason_codes`, labelled):** Campaign pulled forward, Campaign pushed back, Verbal confirmation received, Shelf life constraint, Supplier/supply delay, Retest required, Expedite production requested, Expedite shipping requested, Testing capacity, Other — see notes.
- The preview uses the F11 preview endpoint.

## Functional requirements
| ID | Requirement |
|---|---|
| F19-FR-01 | Five windows (W2–W6) per the layouts above, on the shared `Modal` (Radix Dialog): Esc closes, focus is trapped and returns to the trigger. URLs: `?row=<row_key>` opens the drawer; `?win=<inbound\|quality\|status\|samples\|needby>&row=<row_key>` opens a window and can be deep-linked. A window can open on top of an open drawer, and closing the window leaves the drawer open. One window at a time. The **drawer** is non-modal (560 px, right side): the table stays interactive, a row click swaps its content, and the persona switcher works while it is open |
| F19-FR-02 | **Inbound sub-checks (source):** erp_sim table `zinbchk_item` (`prueflos`, `seq`, `check_code`, `check_label`, `outcome` in `PASS, FAIL, PENDING, NO, COMP, APRV, DCPS`, `updated_at`). `zinbchk.status` gains `resolved` (the check completed with an issue resolved). `inbound-check` events accept items. Datagen: 5–9 items per check from a generic list (Physical evaluation, Inbound delivery check, Supplier batch verification, Quantity received verification, Date verification (expiry/mfg/re-eval/COA), Certificate of analysis, Deviation on batch, Batch use, Results of analytical work). Failed checks have ≥ 1 FAIL. About 8% of passed checks become `resolved`. The pipeline publishes `inbound_checks_v` (`row_key, prueflos, status, deadline, failed_count, items_json`). **Stage engine:** `resolved` behaves like `passed`. Edit 04 §3 so receipt exit = `completed_on` when status IN (`passed`, `resolved`), add R-RCP/R-SMP rule tests for `resolved`, and map `inbound_light` resolved → amber (03 §1/§4/§8). Datagen's `intended_stage` for resolved lots is unchanged (no oracle change). Story batches are excluded from the 8% conversion. Use new `rng.stream` names for every new draw. Agreement must stay at 100% and the F05 report counts must not change |
| F19-FR-03 | **Quality data (source):** qms_sim adds `deviation.causal_factor`, `deviation.investigation_summary`, and severity vocabulary **`minor`, `moderate`, `major`** (migrate `critical` → `major`; the datagen mix is 60/30/10 minor/moderate/major; B3150 stays an open **major**). New tables `change_control` (`cc_no CC-000001`, `title`, `status` open/approved/closed/cancelled, `current_state`, `proposed_state`, `opened_on`, `effective_on`, `updated_at`) and `change_control_link` (`cc_no, material_no, batch_no`). Datagen: ~40 change controls, ~15% of batches linked (at least one on a green batch). The pipeline publishes `change_controls_v`, and `deviations_v` gains the new fields |
| F19-FR-04 | **Samples:** the pipeline publishes `samples_v` (`row_key, sample_id, status, collected_date, approved_at`), with all samples per lot, not just the latest. The overview row gains `sample_count` |
| F19-FR-05 | **Status log:** new app table `status_log` (`id, row_key, status, team, reason_code null, comment, author_user_key, at` (demo clock)), insert-only. `GET/POST /api/rows/{row_key}/status-log`. Migrate existing `manual_status` overrides (`{rag, team}`: green→`on_track`, amber→`at_risk`, red→`blocked`) and `comment` rows (status `null`, displayed without a dot) into it (one-off migration). Keep the old endpoints as thin wrappers, marked deprecated, until F21. Profile `status_options` (key, label, colour) and `status_reasons`. The overview row exposes `latest_status` (status, comment, author, at). Audit actions `status_logged` |
| F19-FR-06 | **Reason codes:** replace site_a `reason_codes` with the 10 labelled codes above (`CAMPAIGN_PULLED_FORWARD, CAMPAIGN_PUSHED_BACK, VERBAL_CONFIRMATION, SHELF_LIFE_CONSTRAINT, SUPPLIER_DELAY, RETEST_REQUIRED, EXPEDITE_PRODUCTION, EXPEDITE_SHIPPING, TESTING_CAPACITY, OTHER`), as `{code, label}`. Migrate existing override rows (`CAMPAIGN_PUSHED_OUT` → `CAMPAIGN_PUSHED_BACK`, `LAB_CAPACITY` → `TESTING_CAPACITY`, other retired codes → `OTHER` with the original code kept in `note`). `OTHER` requires a note (422 otherwise). `reason_codes_v` carries labels |
| F19-FR-07 | **Keep and refactor the F11 drawer** (no deletion of `components/drawer/*`): it becomes the non-modal batch home with the history sections (summary, milestones, timeline, other lots, export) and the summary sections with "Open ↗" links (table above). Batch link, row click, Enter and `?row=` open the drawer. Inbound and deviation dots open W2 and W3. The status icon opens W4. The sample badge opens W5. The adjusted-date cell opens W6. Explain popovers stay. F11's separate Comments and Human input sections are replaced by the Status log and Need-by summaries (FR-05) |
| F19-FR-08 | The drawer and all windows are read from the mirror and app DB only (constitution P2). Every new published object carries `run_id` and is added to `OBJECTS_WITH_RUN_ID` (pipeline publish + app models). Add `run_id` to `deviations_v` if it's missing. The 04 §5 watermark wording becomes "one row per mirrored object". New mirror tables: `mirror_inbound_checks`, `mirror_change_controls`, `mirror_samples`, plus the extended `mirror_deviations`. F08 consistency is updated |

## Contract changes
All the source, published, mirror and app-table additions above go into 04 §1–§5. In 03: the inbound `resolved` status (§1, §4, §8), the severity vocabulary, the profile `status_options`, `status_reasons` and labelled `reason_codes`, and the status log replacing manual status (§6).

## Acceptance criteria
- **F19-AC-01** B4410 → the drawer shows 5 lots under Other lots (Initial, Re-eval 1–3 and the current one, marked), a blue current stage and total days against target. Closing it puts `B4410` into the Batch filter.
- **F19-AC-02** A failed inbound check → W2 shows "Failed checks: n" and the FAIL items in red. A resolved check shows the amber dot and "Completed (Resolved)".
- **F19-AC-03** B3150 → W3 shows Red, "1 open deviation", Open Deviations (1) with a **Major** card, and the severity pills filter it. A green batch with a linked change control shows Changes (1).
- **F19-AC-04** As Quinn, adding status "At Risk", team "QC Lab", reason "Resource constraint" and a comment puts it on top of Latest. The Status cell shows the comment beneath. History counts 2 after a second entry. As Sam the form is disabled.
- **F19-AC-05** B1042 → W5 lists its samples with counts per status. Clicking an ID copies it (clipboard mocked in the test).
- **F19-AC-06** **Act 5:** B2077 → W6, set 26 Nov 2026 with "Campaign pulled forward". The window shows "−7d (pulled forward)" in red and the preview "Sampling: 14 Oct 2026 · QCL Testing: 20 Nov 2026 · QA Release: 26 Nov 2026" (from 6/37/6). Save is disabled before a reason is chosen. After save, the row is italic with a pencil and the system date struck through, and it re-sorts with the save highlight.
- **F19-AC-07** F06 agreement stays at 100%, the datagen determinism test passes with the new source data, and the F05 report counts and week-41 percentages are unchanged.
- **F19-AC-08** Screenshots in `docs/screenshots/`: `drawer-b4410.png` (the table and drawer side by side), `win-inbound-failed.png`, `win-quality-b3150.png`, `win-statuslog.png`, `win-samples-b1042.png`, `win-needby-b2077.png`.
