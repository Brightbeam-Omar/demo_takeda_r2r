"""``artifacts/datagen_report.md``: what was generated, and whether it is within the targets (F05-FR-08)."""

from collections.abc import Mapping

from r2r_core.profile import SiteProfile

from datagen.model import Plan
from datagen.params import Params
from datagen.quirks import quirk_counts
from datagen.stats import METRICS, Stats

STAGE_LABELS = {
    "pending": "Pending",
    "receipt": "Receipt",
    "call_off": "Call Off",
    "sampling": "Sampling",
    "qc_ship": "QC Ship",
    "qc_testing": "QC Testing",
    "qa_release": "QA Release",
}
STORY_SETUP = {
    "B1042": "QC testing onsite, all tests done, LIMS not approved yet",
    "B2077": "sampling since 8 Oct, need-by 3 Dec: no compression until pulled forward",
    "B3150": "QA release with an open major deviation",
    "B4410": "re-evaluation lot in sampling; initial release plus 3 earlier re-evals",
    "B5003": "LIMS approved 30 h before opening, no usage decision (air gap)",
}


def _table(header: list[str], rows: list[list[object]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def _mark(ok: bool) -> str:
    return "yes" if ok else "**NO**"


def render_report(
    plan: Plan,
    profile: SiteProfile,
    params: Params,
    stats: Stats,
    lot_numbers: Mapping[str, str],
    table_counts: Mapping[str, int] | None = None,
    event_counts: Mapping[str, int] | None = None,
    elapsed_seconds: float | None = None,
) -> str:
    cal = plan.calendar
    out: list[str] = ["# Synthetic data report", ""]
    took = f" · replayed in {elapsed_seconds:.1f} s (budget 60 s)" if elapsed_seconds is not None else ""
    out.append(
        f"Profile `{profile.site.code.lower()}` · seed {plan.seed} · demo start "
        f"{profile.demo.start_datetime:%Y-%m-%d %H:%M} ({profile.site.timezone}){took}"
    )
    out += ["", "## Volumes", ""]
    v = params.volumes
    lot_01, lot_09 = stats.lots_by_type.get("01", 0), stats.lots_by_type.get("09", 0)
    reeval_batches = sum(1 for b in plan.batches if any(lot.lot_type == "09" for lot in b.lots))
    out.append(
        _table(
            ["Item", "Count", "Spec (F05-FR-02)", "Note"],
            [
                ["Materials", stats.materials, 300, f"{stats.drug_substance_share:.0%} drug substance"],
                ["Suppliers", stats.suppliers, 40, ""],
                ["Storage locations", stats.locations, "6 (4 onsite, 2 3PL)", ""],
                ["Campaigns", stats.campaigns, 5, ", ".join(plan.world.campaigns)],
                ["Batches (distinct)", stats.batches, f"~{v.batches}", "per batch"],
                [
                    "Inspection lots (rows)",
                    stats.lots,
                    "",
                    f"{lot_01} initial (01) + {lot_09} re-evaluation (09)",
                ],
                ["Re-evaluation lots", lot_09, "~120", f"on {reeval_batches} batches; up to +40% allowed"],
                ["Deviations", stats.deviations, f"~{v.deviations}", f"{stats.open_deviations} open"],
                ["Demand lines", len(plan.demands), "", ""],
                ["Received into a 3PL", f"{stats.threepl_share:.1%}", "~30%", "share of deliveries"],
                ["Offsite tests", f"{stats.offsite_share:.1%}", "~12%", "share of samples"],
            ],
        )
    )
    if table_counts:
        out += ["", "## Rows by table", ""]
        out.append(_table(["Table", "Rows"], [[name, count] for name, count in sorted(table_counts.items())]))
    out += ["", "## Open-row stage mix (intended stage labels)", ""]
    out.append(
        f"{stats.open_rows} open rows (every lot not released) and {stats.released_rows} released rows."
    )
    out.append("")
    rows = []
    for stage, target in params.open_stage_mix.items():
        count = stats.open_stage_counts.get(stage, 0)
        share = count / stats.open_rows
        delta = 100 * (share - target)
        rows.append(
            [
                STAGE_LABELS[stage],
                count,
                f"{100 * share:.1f}%",
                f"{100 * target:.0f}%",
                f"{delta:+.1f}",
                _mark(abs(delta) <= params.stage_tolerance_pp),
            ]
        )
    out.append(
        _table(
            ["Stage", "Rows", "Share", "Target", "Δ pp", f"Within ±{params.stage_tolerance_pp:g} pp"], rows
        )
    )
    out += ["", "## RAG mix (open rows with a plan date, at demo start)", ""]
    rag_total = sum(stats.rag_counts.values())
    rows = []
    for colour, target in params.rag_mix.items():
        share = stats.rag_counts[colour] / rag_total
        delta = 100 * (share - target)
        rows.append(
            [
                colour,
                stats.rag_counts[colour],
                f"{100 * share:.1f}%",
                f"{100 * target:.0f}%",
                f"{delta:+.1f}",
                _mark(abs(delta) <= params.rag_tolerance_pp),
            ]
        )
    out.append(
        _table(["RAG", "Rows", "Share", "Target", "Δ pp", f"Within ±{params.rag_tolerance_pp:g} pp"], rows)
    )
    out += ["", "## Weekly completions and on-time share (the 12 metric weeks)", ""]
    header = ["Week starting"]
    for metric, stage in METRICS.items():
        header += [f"{metric} {stage} done", f"{metric} on-time"]
    rows = []
    for index, week in enumerate(cal.metric_week_starts):
        row: list[object] = [f"{week:%Y-%m-%d}"]
        for metric in METRICS:
            stat = stats.weekly[metric][index]
            row += [stat.completed, f"{stat.pct:.0f}%" if stat.pct is not None else "n/a"]
        rows.append(row)
    out.append(_table(header, rows))
    minimum = params.completions.min_per_week
    fewest = min(w.completed for ws in stats.weekly.values() for w in ws)
    out += [
        "",
        f"Fewest completions in any metric week: {fewest} (needs {minimum}): {_mark(fewest >= minimum)}.",
    ]
    out += ["", "## Quirks", ""]
    counts = quirk_counts(plan, profile)
    out.append(
        _table(["Quirk", "Count", "At least 3"], [[name, n, _mark(n >= 3)] for name, n in counts.items()])
    )
    out += [
        "",
        "Notes:",
        "",
        "- `concurrent_batches_two_campaigns` counts materials with two or more batches in flight",
        "  and open demand for two campaigns. In Tier 1 the pipeline gives all batches of a material",
        "  the campaign of its earliest open demand line (04 section 3): the second campaign shows in",
        "  the ERP demand, not per batch.",
        "- `air_gap`: LIMS approved at least 24 hours ago, no usage decision and no ERP record of the",
        "  results (03 section 6). Normal approvals have their results recorded 1-6 hours later.",
    ]
    gaps = counts["air_gap"]
    out += ["", f"Air gaps at demo start: {gaps} (target 3 to 5): {_mark(3 <= gaps <= 5)}."]
    out += ["", "## Story batches", ""]
    story_rows: list[list[object]] = []
    for batch in plan.batches:
        if batch.story_id:
            lot = batch.lots[-1]
            numbers = ", ".join(lot_numbers.get(x.ref, x.ref.split("|", 2)[2]) for x in batch.lots)
            story_rows.append(
                [
                    batch.charg,
                    batch.matnr,
                    STAGE_LABELS.get(lot.stage, lot.stage),
                    numbers,
                    STORY_SETUP[batch.charg],
                ]
            )
    out.append(_table(["Batch", "Material", "Stage", "Inspection lot(s)", "Set-up"], sorted(story_rows)))
    if event_counts:
        out += ["", "## Events replayed through the F04 event functions", ""]
        out.append(_table(["Event", "Count"], [[name, n] for name, n in sorted(event_counts.items())]))
    return "\n".join(out) + "\n"
