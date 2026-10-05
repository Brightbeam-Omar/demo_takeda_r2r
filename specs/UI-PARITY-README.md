# UI Parity Pack (F15–F21)

**Purpose:** bring the demo UI to parity with the as-built R2R dashboard, using the generic vocabulary and no client branding. These features slot in **after F11 and before F12**, so the agent screens (F12), the scenario steps (F13) and the run-of-show (F14) are built on the final design.

**Files to copy into the repo (once F11 is merged and Claude Code is stopped):**
- `specs/05-ux-guidelines.md`: **replaces** the current file (v2, parity visual system)
- `specs/features/F15-ui-shell-terminology/` … `specs/features/F21-sync-admin-pages/`

**Roadmap rows to add** (status `ready`, Tier 1). F12 then depends on F21.

| ID | Feature | Depends on |
|---|---|---|
| F15 | UI shell, visual system & profile terminology | F11 |
| F16 | Overview I: filter panel, presets, bookmarks, alert banners | F15 |
| F17 | Overview II: stage cards (incl. Expected Delivery), metric cards, tag row | F16 |
| F18 | Overview III: pipeline table parity, row actions, exports | F17 |
| F19 | Batch windows: History, Inbound, Quality, Status Log, Sample Data, Adjust Needs-by | F18 |
| F20 | Reports & Metrics page (6 tabs) | F19 |
| F21 | Sync Status, Webhook Sync Status & Admin pages | F20 |

**Reference screenshots are deliberately not included.** They contain client branding and data. Every layout is described in text and ASCII in the specs.

Each feature lists its **contract changes** (to `04-data-contracts.md`, `03-domain-model.md` and the site profile). Claude Code applies them in the feature's first `docs(specs)` commit, because the repo's copies of 03/04 are newer than this pack.

## Deltas to existing specs (apply in F15's first `docs(specs)` commit)
- **Roadmap:** add F15–F21 as above. **F12 depends on F09 (API) and F21 (UI).** F13 depends on F12. T2-01 (if present) depends on F21 for the UI parts: its "seven active chips" become seven parity metric cards.
- **F12-FR-13** becomes: the Insights window (F16-FR-09) gains a **Proposal** column showing the agent proposal status with a link to the proposal, and W1 Batch History (F19) shows a proposal-status line. The old alert-band and drawer links are gone.
- **F13-FR-06:** Demo Controls live at `/admin/demo` (ADMIN menu item "Demo Controls", `DEMO_MODE` and admin only, added in F15).
- **F14:** the run-of-show acts use the parity UI. Act 5 is W6 Adjust Needs-by on B2077. Act 6 runs the agent from the Insights window and Agents page. "Explain this number" uses the ⓘ popovers.
- **03 §9 vocabulary rule** (F15): vendor platform names such as SAP may appear only as profile `terms` values and stage labels.

## Decisions taken in this pack (record as OQs when applied)
- Terminology default **SAP** for site_a (product-owner decision). Generic in code and data.
- ADMIN visible to all roles, with admin-only actions gated (supersedes OQ-063's hide rule).
- Status log open to all non-viewer roles (supersedes OQ-071's status roles).
- `on_hold` stays the ERP fact. `manual_hold` is app-side, and `on_hold_display` drives the UI and sorting.
- Place Hold / Release on COA are role-gated (the as-built had no check; the demo's governance story is stronger with one).
- 7 metrics kept (the as-built showed 6). M1 Receipt stays.
- Expedite history comes from **source facts** (ERP), never seeded app overrides.
- All new datagen draws use new `rng.stream` names. The F05 report counts and week-41 percentages must not move.
