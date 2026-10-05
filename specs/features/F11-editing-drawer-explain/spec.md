# F11 · Editing, Batch Drawer, Explain, Sync Status & Audit Pages

## Functional requirements
| ID | Requirement |
|---|---|
| F11-FR-01 | **Batch drawer** (row click): header (material, batch, lot, stage chip, tags), sections: *Timeline* (stage entry/exit with days per stage vs SLA; sibling lots of the same batch listed in order, e.g. initial + re-evals), *Plan* (operative need-by, expected completion, compression, RAG), *Quality* (deviations list with severity/status; inbound check), *Human input* (current overrides and full version history), *Comments* (list + add), *Source refs* (collapsed) |
| F11-FR-02 | **Need-by edit modal** per the UX guide. It calls a **preview** endpoint before save: add `POST /api/rows/{row_key}/need-by/preview` to F09 (same body, any identified role, reason not required, no writes, returns the plan after the change plus the current plan; OQ-067). Saving shows a toast and the table re-sorts with the row highlighted for 5 s by a separate "just saved" highlight (OQ-070) |
| F11-FR-03 | **Status edit** (RAG + reason + team) for `qc_lead`, `qa_release` and `admin`, and comment entry for every role except viewer. Other roles see the controls disabled with "Read-only role" (OQ-071) |
| F11-FR-04 | **Explain popover** on: stage chip, expected completion, each metric chip, each flow-strip count. The table ⓘ shows on row hover and focus; flow cards and metric chips get a small corner ⓘ with its own hit target, separate from click-to-filter (OQ-069). Content per F09 explain payloads and the UX guide, and copyable |
| F11-FR-05 | **Sync Status page** (`/sync`). `run_id` is the Dagster run id: pipeline status card (last run id, last success, freshness, per-source freshness table), watermark table, last 50 sync events with status chips and durations (shown as relative ages and durations such as "2 min ago" and "1.4 s", never as absolute dates, because sync times are wall-clock and must not clash with the demo date on screen; the API gives `age_seconds` and `duration_ms`), an admin-only "Trigger sync" button, and a link to the Dagster UI run (`<VITE_DAGSTER_URL>/runs/<run_id>`, default `http://localhost:3001`, OQ-073) |
| F11-FR-06 | **Audit Log page** (`/audit`): filterable table (actor, action, row, date range via `from`/`to`), with expandable details (old → new from `details_json`; OQ-068) |
| F11-FR-07 | Deep link: `/overview?row=<row_key>` opens the drawer, which loads from `/api/rows/{row_key}` independently so it works when the row is filtered out (OQ-072) |

## Acceptance criteria
- **F11-AC-01** (Playwright, act 5) As Pat, open B2077, set need-by 2026-12-03 → 2026-11-26 with `CAMPAIGN_PULLED_FORWARD`. The preview shows compression 6/37/6 and expected 14 Oct (amber) before save. After save, the table shows the adjusted date italic with the system date struck through, and the audit log has the entry with old/new values.
- **F11-AC-02** As Sam, the drawer shows no enabled edit controls, and a forced API call returns 403 (covered by F09, the UI shows the tooltip).
- **F11-AC-03** B4410 drawer timeline shows the initial lot plus 3 earlier re-evals and the current re-eval.
- **F11-AC-04** Explain on M3 (last complete week) lists contributing batches, and the count matches that week's `completed`.
- **F11-AC-05** After a pipeline run, the Sync page shows a new `webhook` event moving `pending → done` within the drain interval, and the watermark updates.
- **F11-AC-06** B3150 drawer shows the open major deviation, and the row's deviation light is red.
