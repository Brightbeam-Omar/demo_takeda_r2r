# F20 · Reports & Metrics Page

## Context
The as-built dashboard's second view: "are we hitting our targets, and is it getting better or worse?" Six tabs and a year selector. All figures come from published facts (pipeline) or from read-time maths in `r2r_core` (where human input such as adjusted need-by dates or expedites matters). There is no hand-entered number.

## Layout
`Reports & Metrics` page:
- a tab row `Executive Summary · SLA Performance · Trends · Late Items · Release Rate · Adherence to NBD`, with `Year [2026 ▾]` on the right;
- an info banner listing metrics that have no signal ("M1, M2, M4, M5 show N/A until their feeds are connected", hidden once T2-01 is done);
- `[↓ Export]` (CSV of the figures behind the current tab) on every tab.

| Tab | Content |
|---|---|
| **Executive Summary** | Three cards for the year to date, each with a big figure, a progress bar with a target marker, and counts beneath. **Release Rate:** released lots YTD / annual target (e.g. "318 / 700"), with the bar marker at the **pro-rata target for the covered period** and the caption "n% of pro-rata target" (e.g. 318 against a pro-rata target of 350 at 26 coverage weeks reads "91% of pro-rata target"). **Needs-by Adherence:** released lots with a need-by at release that were released on or before it (e.g. "280 on-time / 31 late"). **Expedite On-Time Rate:** expedited lots released on or before their expedite due date (e.g. "3 on-time / 4 expedited"), with the note "Tracked separately from the standard M1–M7 metrics — a missed expedite does not penalise the standard SLA" |
| **SLA Performance** | One vertical bar per metric showing the last complete period's on-time %, with a dashed target line at `metric_rag.green_min_pct` (90%), a value label, and "M3: Sampling" captions. N/A bars show the `null_reason` text beneath |
| **Trends** | (a) **SLA Trends table:** one row per metric. With Weekly selected, the last 4 complete weeks + current; with Monthly, the last 3 months + current. Cells are shaded green or red by threshold. A **Trend** column shows ▲ +n% green, ▼ −n% red, "Stable" (|Δ| < 2 pp) or "—" (insufficient data), comparing the last complete period with the one before. (b) **Pipeline Stage Trends:** a stacked bar per day (Daily) or per week (Weekly) of open rows by stage, using stage colours, a legend, and a range scrubber across the year |
| **Late Items** | A `DataTable` of currently late rows, worst first. Columns: Material · Campaign · Current Stage · Metric Breached (the metric bound to the current stage, else "—") · **Days Over SLA** (red) · Late-Reason Category (latest status-log reason label, else the auto late reason, else "—"). Search, filters and export |
| **Release Rate** | A line of lots released per ISO week, with point labels and a horizontal **weekly target** line (profile), plus a range scrubber |
| **Adherence to NBD** | A stacked bar per week of released lots split into "Within needs-by" and "Exceeded needs-by", with a legend |

## Functional requirements
| ID | Requirement |
|---|---|
| F20-FR-01 | **Profile targets:** `targets: {release_annual: 700, release_weekly: 13, needs_by_adherence_pct: 90, expedite_on_time_pct: 90}` (site_a). The validator requires positive values |
| F20-FR-02 | **Pipeline facts:** (a) `weekly_metrics_v` keeps **52 weeks** (was 12), and a new `monthly_metrics_v` (`metric_id, month_start, completed, on_time, pct, run_id`) is published by the pipeline. The app never recomputes metric maths. (b) New `pipeline_daily_v` (`day, stage_key, open_count`) for the last 365 days up to the snapshot date, joining a calendar table `intelligence.calendar` that `setup` writes in Python (avoiding non-portable date-spine SQL), **derived from the stage entry/exit dates in the snapshot** (a lot is in stage *s* on day *d* if entry ≤ d < exit, or exit is null). It doesn't depend on historical snapshots, so it's deterministic. (c) New `releases_weekly_v` (`week_start, released_count`) from `ud_date` with an effective UD. (d) New `batch_pipeline_v` facts: `need_by_at_release` (earliest `mdez.bdter ≥ gr_date` for the material, **including closed demand lines**; datagen keeps closed lines for released batches) and the **source expedite facts** `expedite_requested_on` and `expedite_due_date` (new ERP `mcha.zexprq`, `mcha.zexpdd`, written by a new ERP event `expedite-requested`; datagen creates ≥ 4 historic expedites, one missed). All new objects carry `run_id`, join `OBJECTS_WITH_RUN_ID`, and use portable SQL with sqlglot tests |
| F20-FR-03 | **App read-time maths** in `r2r_core.reports` (pure, 100% branch coverage): `needs_by_adherence(rows, overrides, year)`, `expedite_on_time(rows, overrides, year)`, and `late_items(rows, plans, status_log)`. Adherence uses `need_by_at_release`, replaced by an adjusted need-by when a need-by override **created before `ud_date`** exists. Expedite on-time uses the source expedite facts (released on or before `expedite_due_date`), plus any app expedite overrides on rows released since. **No historic app overrides are seeded.** |
| F20-FR-04 | **Coverage:** the year selector lists years with any data. Because the synthetic history starts ~26 weeks before demo start, the page shows a muted note "Coverage from <first date>" (parity with the as-built "coverage still being filled") |
| F20-FR-05 | **Charts:** Recharts (approved dependency), styled with the v2 tokens and readable at 1440×900. No interactions beyond hover tooltips and the range scrubber |
| F20-FR-06 | **Endpoints:** `GET /api/reports/{summary|sla|trends|late|release-rate|adherence}?year=&grain=`, each returning `contract_run_id` and freshness, and `GET /api/reports/{tab}/export.csv` |
| F20-FR-07 | **Datagen tuning** (new `rng.stream` names only): adherence between 85% and 89.9% (amber against 90) and exactly 4 historic expedites, 3 on time and 1 missed (OQ-122). **Release volumes are not retuned. The F05 report counts and the week-41 percentages must not change** |

## Contract changes
- **03 §2:** `targets`. **03 §7:** a 52-week metric history and `monthly_metrics_v`. **03 §1/§6:** expedite source facts.
- **04 §1.1:** `mcha.zexprq` and `mcha.zexpdd`, the `expedite-requested` event, and closed demand lines kept. **04 §2:** `intelligence.calendar`. **04 §3/§4.1:** `need_by_at_release`, `expedite_requested_on`, `expedite_due_date`. **04 §4:** `monthly_metrics_v`, `pipeline_daily_v` and `releases_weekly_v`. **04 §5:** their mirror tables.
- **F08:** consistency for the new objects.

## Acceptance criteria
- **F20-AC-01** Executive Summary shows Release Rate YTD = count of released lots with `ud_date` in 2026 (an API test against the mirror), with the pro-rata target marker computed from `release_annual` × coverage weeks / 52.
- **F20-AC-02** SLA Performance shows M3 green, M6 amber, M7 red for week 41, with the 90% dashed line.
- **F20-AC-03** Trends Weekly shows 4 complete weeks + current, with ▲/▼ computed as specified (a fixture test). Monthly pools match a hand-computed fixture.
- **F20-AC-04** Pipeline Stage Trends: the latest day's stacked total equals the open **non-pending** rows (468 at demo start; pending rows have no stage dates).
- **F20-AC-05** Late Items: the count equals the Overview's late count, worst first. After Quinn logs "Resource constraint" on a late row, its Late-Reason Category shows it.
- **F20-AC-06** Adherence: after the B2077 pull-forward the figures don't change, because B2077 isn't released. A fixture with a release after its adjusted date counts as exceeded.
- **F20-AC-07** Screenshots of each tab in `docs/screenshots/reports-*.png`.

## Decisions (OQ-117 to OQ-126)
Coverage, lot counting, need-by anchoring, expedite scope, override timing, late-item definitions, grain parameters (`grain=weekly|monthly`, `stage_grain=daily|weekly`), the one-stage-per-day rule and the export and banner rules are in `OPEN_QUESTIONS.md` and in 03 §7.1 and 04 §4.2c. The year selector filters Executive Summary, Release Rate and Adherence only. SLA Performance, Trends and Late Items are as of the demo date.
