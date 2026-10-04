"""T6 [TDD]: volumes, stage mix, RAG mix and weekly completions (F05-FR-02..04, F05-AC-02)."""

import pytest
from datagen.model import Plan
from datagen.params import Params
from datagen.stats import compute_stats
from r2r_core.profile import SiteProfile


@pytest.fixture(scope="module")
def stats(plan: Plan, profile: SiteProfile):  # type: ignore[no-untyped-def]
    return compute_stats(plan, profile)


def within_pp(actual: float, target: float, tolerance_pp: float) -> bool:
    return abs(100 * (actual - target)) <= tolerance_pp


def test_f05_ac02_fr02_volumes_are_inside_the_allowed_range(stats, params: Params) -> None:  # type: ignore[no-untyped-def]
    volumes = params.volumes

    def allowed(base: int) -> tuple[float, float]:
        return base * 0.9, base * 1.4  # +-10%, and the decided uplift of up to 40%

    assert stats.materials == 300
    assert stats.suppliers == 40
    assert stats.locations == 6
    assert stats.campaigns == 5
    low, high = allowed(volumes.batches)
    assert low <= stats.batches <= high
    reeval_lots = stats.lots_by_type["09"]
    low, high = allowed(120)
    assert low <= reeval_lots <= high
    low, high = allowed(volumes.deviations)
    assert low <= stats.deviations <= high
    assert stats.lots == sum(stats.lots_by_type.values())
    assert 0.80 <= stats.drug_substance_share <= 0.90


def test_f05_ac02_fr03_open_stage_mix_is_within_three_points_of_target(stats, params: Params) -> None:  # type: ignore[no-untyped-def]
    assert stats.open_rows == sum(stats.open_stage_counts.values())
    for stage, target in params.open_stage_mix.items():
        share = stats.open_stage_counts.get(stage, 0) / stats.open_rows
        assert within_pp(share, target, params.stage_tolerance_pp), (stage, share, target)


def test_f05_ac02_fr03_rag_mix_is_within_five_points_of_target(stats, params: Params) -> None:  # type: ignore[no-untyped-def]
    total = sum(stats.rag_counts.values())
    assert total == stats.open_rows - stats.open_stage_counts["pending"]
    for rag, target in params.rag_mix.items():
        assert within_pp(stats.rag_counts[rag] / total, target, params.rag_tolerance_pp), (
            rag,
            stats.rag_counts,
        )


def test_f05_fr03_threepl_and_offsite_shares_are_about_right(stats, params: Params) -> None:  # type: ignore[no-untyped-def]
    assert within_pp(stats.threepl_share, params.mix.threepl_share, 5)
    assert within_pp(stats.offsite_share, params.mix.offsite_share, 3)


def test_f05_fr03_released_rows_come_from_the_history(stats) -> None:  # type: ignore[no-untyped-def]
    assert stats.released_rows > 0
    assert stats.released_rows + stats.open_rows == stats.lots


@pytest.mark.parametrize("metric", ["M3", "M6", "M7"])
def test_f05_fr04_every_metric_week_has_enough_completions_and_a_plausible_on_time_share(
    stats,  # type: ignore[no-untyped-def]
    params: Params,
    metric: str,
) -> None:
    weeks = stats.weekly[metric]
    assert len(weeks) == params.history.metric_weeks
    assert all(w.completed >= params.completions.min_per_week for w in weeks), weeks
    shares = [100 * w.on_time / w.completed for w in weeks]
    assert min(shares) >= 65 and max(shares) <= 95, shares
    assert max(shares) - min(shares) >= 5  # the percentages vary from week to week


def test_f05_fr04_overall_on_time_is_about_80_percent(stats) -> None:  # type: ignore[no-untyped-def]
    for metric in ("M3", "M6", "M7"):
        weeks = stats.weekly[metric]
        overall = sum(w.on_time for w in weeks) / sum(w.completed for w in weeks)
        assert 0.75 <= overall <= 0.85, (metric, overall)
