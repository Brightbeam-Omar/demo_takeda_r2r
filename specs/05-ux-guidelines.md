# 05 · UX Guidelines (v2: parity with the as-built dashboard)

v2 replaces v1. The demo's UI matches the as-built R2R dashboard in layout, components and behaviour, with generic branding and vocabulary. If anything here conflicts with an F10/F11 decision, v2 wins from F15 onwards.

## 1. Principles (unchanged)
Exceptions first. Show the provenance (every number explains itself). Screen-share legible at 1440×900. Calm by default (colour carries meaning).

## 2. Visual system
| Token | Value |
|---|---|
| Canvas | white `#FFFFFF`. Panels `#F8F9FB`. Hairlines `#E5E7EB` |
| Text | primary `#111827`, secondary `#6B7280`, muted `#9CA3AF` |
| Accent | indigo `#4F46E5` (selected pills, links, primary buttons), with a lavender tint `#EEF0FF` for selected cards |
| Font | **DM Sans** (self-hosted via `@fontsource/dm-sans`). Base 14 px, table 13 px, labels 11 px uppercase with letter-spacing (e.g. "STAGE 2", "METRIC 3", column headers) |
| Radius | pills 9999 px, cards 10 px, modals 12 px |
| RAG | green `#16A34A`, amber `#D97706`, red `#DC2626`, grey `#9CA3AF` (dots 8 px) |
| Exception row | tint `#FEF2F2` with a 3 px red left bar |
| Tag colours | LATE red outline · REJECTED dark-red filled · ON HOLD red filled · RE-EVAL blue filled · EXPEDITE orange outline · FULL SPEC purple outline · OFFSITE TEST blue outline · RELEASE ON COA green outline · ERP BLOCKED amber filled · RELEASED green outline · AIR GAP red outline. Selected filter tags fill with their colour |
| Stage badge | a pill in the stage's colour (light tint + strong text), the same colour as its stage card when selected |

**Branding:** a generic wordmark ("R2R Intelligence" with a simple mark) in the top-left logo slot. **Never a client logo.** System names in UI copy come from the profile `terms` (§6).

## 3. Shell
```
┌────────────┬───────────────────────────────────────────────────────────────────────┐
│ [mark] R2R │ R2R Overview  ● All feeds current — last sync 12 min ago   Period: [📅 All Dates ▾]  12/10/2026 08:00  👤 Pat · Planner │
│ Phase 1:   ├───────────────────────────────────────────────────────────────────────┤
│ Trusted    │                                                                       │
│ Data [ALPHA – LOCAL]                                                               │
│ VIEWS      │                               page content                            │
│  Overview  │                                                                       │
│  Reports & Metrics                                                                 │
│  Agents    │                                                                       │
│ ADMIN      │                                                                       │
│  Team Dashboard · Audit Log · Schema Reference · Upload Data · Process / Campaign  │
│  Mapping · POC — Integrations · Configuration · SLA Configuration · Sync Status ·  │
│  Webhook Sync Status · Demo Controls (DEMO_MODE, admin only)                       │
│ (DEMO) Persona [Pat · Planner ▾]                                       [💬 Feedback]│
└────────────┴───────────────────────────────────────────────────────────────────────┘
```
- The sidebar is light (white, with a hairline right border) and 232 px wide. Menu groups VIEWS and ADMIN have uppercase muted labels. The active item has a lavender background and indigo text.
- The release badge names the environment: `ALPHA – LOCAL` (dev), `ALPHA – DEMO` (AWS).
- Top bar: page title · feed-status pill (green dot "All feeds current — last sync N min ago"; amber/red per freshness rule) · "Period:" selector · demo date-time `dd/mm/yyyy HH:MM` · user "Name · Role".
- A floating **Feedback** button sits bottom-right on every page.

## 4. Overview page (top to bottom)
1. **Filter bar:** `[▴ Filters]  [☆ Bookmarked]  [⚲ Presets]`. When expanded, a panel shows rows of pills:
   - `Type  (All) Small Molecule  Large Molecule  Peptides`
   - `Class (All) Consumable  Drug Substance  Unknown`
   - `Campaign [Filter campaigns…] (All) CMP-ALPHA (12) CMP-BRAVO (9) …` (scrollable; a `▤ Dropdown view` toggle)
   - When collapsed, a row of chips: `Type: Small Molecule ×  Class: 2 classes ×  Stage: Sampling ×  Clear all`
2. **Alert banners**, full width. Blue when empty ("No adjusted needs-by dates in this period"):
   - `📅 10 adjusted needs-by dates (planner overrides, across all stages)  [View details]`, blue
   - `ⓘ LIMS–ERP Insights (5 batches)  [View all 5 →]`, red when > 0
3. **Pipeline by Stage**, with the header `Pipeline by Stage … [✕ Clear 3 stages]  N active batches` and the caption `▦ Snapshot — all active batches`:
   ```
   ┌╌╌╌╌╌╌╌╌┐ ┌────────┐   ┌────────┐ ▸ ┌────────┐ ▸ ┌────────┐ ▸ … ▸ ┌────────┐ │ ┌────────┐
   ╎STAGE 0 ╎ │ALL     │ │ │STAGE 1 │   │STAGE 2 │   │STAGE 3 │       │STAGE 7 │ │ │   ⚠    │
   ╎Expected╎ │STAGES  │   │Receipt │   │Call Off│   │Sampling│       │Released│   │On Hold │
   ╎Delivery╎ │Total   │   │  39    │   │  58    │   │  87    │       │  321   │   │  12    │
   ╎  23    ╎ │Pipeline│   │12 late │   │25 late │   │28 late │       │        │   │Frozen  │
   ╎Due this╎ │ 482    │   │        │   │31 skip │   │        │       │        │   │batches │
   ╎period  ╎ │Active  │   │        │   │call-off│   │        │       │        │   │        │
   └╌╌╌╌╌╌╌╌┘ └────────┘   └────────┘   └────────┘   └────────┘       └────────┘   └────────┘
   ```
   - Dashed border for Expected Delivery. Grey cards when unselected, lavender tint with an indigo outline when selected. On Hold is amber.
   - **Multi-select.** Selecting stages filters the table, not the cards.
4. **Weekly metrics.** The header reads `Week 41 (2026) — 7 R2R Metrics`, with `Source: weekly_metrics_v` in monospace on the right. Each card shows:
   - `METRIC n` (muted) / name / **big %** / `SLA · on_time/completed ⓘ`
   - a 4 px top bar: green (≥ green threshold), amber (≥ amber threshold), red below, none if N/A
   - `4-wk` beside the label for windowed metrics
5. **Showing line:** `Showing: All in-flight batches` (or `3 stages selected`, `2 tags`, …).
6. **Tag row:** `ALL  LATE  ON HOLD  REJECTED  RE-EVAL  EXPEDITE  FULL SPEC  OFFSITE TEST  RELEASE ON COA  <ERP> BLOCKED  AIR GAP  RELEASED  [Clear tags]`.
7. **Table toolbar** (repeated at the bottom):
   - `[↓ Export ▾] [↓ Export Sampling Plan] [↓ Export QC Testing Queue] [▥ Columns] [⌕ Search all columns…]  1–50 of 803 lots  [↺ Reset Table]`
   - pagination `« ‹ Prev  Page 1 of 17  Next › »  Rows per page [50]`
8. **Table.** The title reads "Pipeline — Exceptions First". Headers are uppercase, with sort arrows and a filter box under each. Columns are in F18.

## 5. Windows (modals)
Centred modal, 720–880 px wide, max height 85 vh with internal scroll, title `<Window> — <batch>`, × close, Esc closes, focus trapped. A grey summary panel sits at the top of each. Specified in F19.

## 6. Terminology (profile `terms`)
All UI copy that names a system or step reads `terms` from the profile. **Vocabulary rule (amends 03 §9, decided by the product owner):** widely used commercial platform names (e.g. SAP) may appear **only** as values of profile `terms` and stage labels. They never appear in code, data, fixtures or commits, and client-internal platform names never appear anywhere. site_a values:
`erp: "SAP"`, `lims: "LIMS"`, `qms: "QMS"`, `qc_lab: "QCL"`, `insights_banner: "LIMS–SAP Insights"`, `erp_blocked_tag: "SAP BLOCKED"`, `planner_overrides: "planner overrides"`. Stage labels come from `stages[].label` (site_a: "QCL Ship For External Testing", "QCL Testing"). The data model and code keep generic names (`erp_*`).

## 7. Copy
Dates `12 Oct 2026` in tables, and `dd/mm/yyyy HH:MM` in the top bar. Durations `5d`. Overdue `LATE +12d`, `17 Aug 2026 (56d over)`. A dash (—) means no value. Sync pages show relative ages and durations only (OQ-054).
