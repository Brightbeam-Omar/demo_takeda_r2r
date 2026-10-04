"""T8: the generated artefacts carry no client terms (F05-AC-06)."""

from pathlib import Path

from datagen.legacy_workbook import build_workbook
from datagen.model import Plan
from datagen.oracle import oracle_rows, write_oracle
from datagen.params import Params
from datagen.report import render_report
from datagen.stats import compute_stats
from leakscan.cli import main as leakscan
from r2r_core.profile import SiteProfile


def test_f05_ac06_the_leak_scan_of_the_generated_artefacts_is_clean(
    plan: Plan, params: Params, profile: SiteProfile, tmp_path: Path
) -> None:
    stats = compute_stats(plan, profile)
    build_workbook(plan, params, stats).save(tmp_path / "legacy_tracker.xlsx")
    write_oracle(tmp_path / "expected_stages.csv", oracle_rows(plan, None))
    numbers = {lot.ref: lot.ref.split("|", 2)[2] for _, lot in plan.lots()}
    (tmp_path / "datagen_report.md").write_text(render_report(plan, profile, params, stats, numbers))
    assert leakscan([str(tmp_path)]) == 0


def test_f05_fr08_the_report_can_be_rendered_from_the_plan_alone(
    plan: Plan, params: Params, profile: SiteProfile
) -> None:
    numbers = {lot.ref: lot.ref.split("|", 2)[2] for _, lot in plan.lots()}
    text = render_report(plan, profile, params, compute_stats(plan, profile), numbers)
    assert "**NO**" not in text
