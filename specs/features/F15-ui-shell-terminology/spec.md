# F15 · UI Shell, Visual System & Profile Terminology

## Context
This is the first UI-parity feature (see `05-ux-guidelines.md` v2). It re-skins the app frame to match the as-built dashboard: a light sidebar with VIEWS and ADMIN groups, the parity top bar, the period picker, DM Sans, and a Feedback button. It also makes every system name in UI copy come from the site profile, so an SAP site reads "SAP" and another site can read "ERP".

## Functional requirements
| ID | Requirement |
|---|---|
| F15-FR-01 | Visual tokens per 05 v2 §2 as Tailwind theme extensions. Swap Inter for DM Sans (`@fontsource/dm-sans`, weights 400/500/600/700). Remove the dark sidebar styles |
| F15-FR-02 | Sidebar per 05 v2 §3: wordmark slot, "Phase 1: Trusted Data", and a release badge from env `RELEASE_BADGE` (default `ALPHA – LOCAL`). Groups: **VIEWS** (Overview, Reports & Metrics, Agents) and **ADMIN** (Team Dashboard, Audit Log, Schema Reference, Upload Data, Process / Campaign Mapping, POC — Integrations, Configuration, SLA Configuration, Sync Status, Webhook Sync Status, and **Demo Controls** (shown only in `DEMO_MODE` and to `admin`; F13 fills it)). The ADMIN group is visible to every role (parity; **record an OQ that supersedes OQ-063's 'Admin hidden unless admin'**), and admin-only *actions* stay gated. Routes for items not built yet render a titled placeholder ("Coming in F20/F21" or "Tier 2"). It collapses to icons with `«` |
| F15-FR-03 | Top bar per 05 v2 §3. Page title per route ("R2R Overview", "Reports & Metrics", …). The feed pill text is "All feeds current — last sync N min ago" (green), "Feeds stale — last sync N h ago" (amber 6–12 h) or "Feeds stale — last sync N h ago" (red > 12 h), using the F10 demo-time rule. The date-time is `dd/mm/yyyy HH:MM` from the demo clock. User chip "Name · Role" |
| F15-FR-04 | **Period picker** (parity): button `📅 <label> ▾` opens a popover with a left column **Quick Select** (This Week, Last Week, Next Week, This Month, Last Month, Next Month, All Dates; the active option highlighted) and a **two-month calendar** (‹ ›, today ringed). A range is picked by first date then last date, with the hint "Click a date to start" → "Click an end date". **Apply** is disabled until the range is valid. It maps onto the existing period params (`last_month` and `next_month` are new values; extend F09 `period` additively) |
| F15-FR-05 | **Profile terminology:** add `terms` to the site profile model (optional keys with generic defaults: `erp`, `lims`, `qms`, `qc_lab`, `insights_banner`, `erp_blocked_tag`, `planner_overrides`). `site_a.yaml` sets the SAP-site values from 05 v2 §6. `/api/reference` returns `terms`, and the frontend exposes `useTerms()`. Type and Class pill labels come from the profile `molecule_types`/`material_classes` (add `label` fields), with "Unknown" for NULL only. Every UI string that names a system uses it (e.g. tag "SAP BLOCKED", banner "LIMS–SAP Insights", column "System Needs-By"). The site_a stage labels for qc stages become "QCL Ship For External Testing" and "QCL Testing" |
| F15-FR-06 | **Feedback** floating button on every page → a small modal (message, optional page context auto-filled) → `POST /api/feedback` (any identified role). New `feedback` table (`id, at, user_key, page, message`). Admin can list feedback at `/admin/feedback` (simple table) |
| F15-FR-07 | Persona switcher kept **only when `DEMO_MODE`**, in the sidebar footer, styled per v2 |
| F15-FR-08 | Existing pages (Overview, Sync, Audit, drawer from F11) keep working under the new shell, restyled with tokens only. Their structure changes in F16–F21 |

## Contract changes (apply in the first `docs(specs)` commit)
- **03 §2 profile:** add the `terms` block, with defaults and site_a values. **03 §9:** add the vocabulary rule from 05 v2 §6 (vendor platform names only as profile `terms` values). Record it as an OQ decision by the product owner. Constitution P5 is unchanged in intent, so add one clarifying sentence.
- **04 §5 app DB:** add the `feedback` table.
- **F09 API:** add `period` values `last_month` and `next_month`, add `terms` to `/api/reference`, and add the `POST/GET /api/feedback` endpoints.
- Replace `specs/05-ux-guidelines.md` with v2.

## Acceptance criteria
- **F15-AC-01** (Playwright, 1440×900) The sidebar shows the VIEWS and ADMIN groups with every item listed in FR-02, and the badge reads `ALPHA – LOCAL`. Screenshot `docs/screenshots/shell.png`.
- **F15-AC-02** The period picker: choosing "Last Month" applies it, and the label and the Overview counts change. A custom range needs two clicks before Apply is enabled.
- **F15-AC-03** With site_a, the tag reads "SAP BLOCKED" and the stage card reads "QCL Testing". With a test profile whose `terms.erp` is "ERP", it reads "ERP BLOCKED" with no code change.
- **F15-AC-04** Feedback submitted as Sam is stored and listed on `/admin/feedback` for Admin.
- **F15-AC-05** No Inter font requests. Lighthouse accessibility ≥ 90 still holds.
- **F15-AC-06** The leak scan is clean. No client logo asset exists in `frontend/`.
