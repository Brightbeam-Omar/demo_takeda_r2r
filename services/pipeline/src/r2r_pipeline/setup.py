"""The ``setup`` step: record the run's start (F07-FR-05).

Every later step is handed only the ``run_id`` and ``snapshot_date`` (OQ-046). They rebuild the context from
those two values and read what they need from the run log.
"""

from pathlib import Path

from r2r_core.profile import SiteProfile

from r2r_pipeline.context import RunContext, SourceDsns, new_context
from r2r_pipeline.reports import write_calendar
from r2r_pipeline.runlog import StepResult, run_step


def setup(
    profile: SiteProfile,
    lake_root: Path,
    *,
    run_id: str | None = None,
    dsns: SourceDsns | None = None,
) -> RunContext:
    """Create the run context (snapshot date = the demo's today) and write the ``setup`` log row."""
    ctx = new_context(profile, lake_root, run_id=run_id, dsns=dsns)
    run_step(
        ctx,
        "setup",
        lambda: StepResult(
            rows=write_calendar(ctx),
            detail={"snapshot_date": ctx.snapshot_date.isoformat(), "site": profile.site.code},
        ),
    )
    return ctx
