"""The run context shared by the pipeline steps. Plain data, no Dagster."""

import os
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from r2r_core import clock
from r2r_core.db import postgres_dsn
from r2r_core.profile import SiteProfile


@dataclass(frozen=True)
class SourceDsns:
    erp: str
    lims: str
    qms: str

    @staticmethod
    def from_env() -> "SourceDsns":
        """Same variables as the simulators: ``ERP_SIM_DSN`` etc., else built from ``POSTGRES_*``."""
        return SourceDsns(
            erp=os.environ.get("ERP_SIM_DSN") or postgres_dsn("erp_sim"),
            lims=os.environ.get("LIMS_SIM_DSN") or postgres_dsn("lims_sim"),
            qms=os.environ.get("QMS_SIM_DSN") or postgres_dsn("qms_sim"),
        )


@dataclass
class RunContext:
    """``run_id`` is the Dagster run id under Dagster and a uuid4 in plain runs and tests."""

    run_id: str
    profile: SiteProfile
    snapshot_date: date  # the demo's today
    lake_root: Path
    dsns: SourceDsns | None = None
    freshness: dict[str, dict[str, Any]] = field(default_factory=dict)


def new_context(
    profile: SiteProfile,
    lake_root: Path,
    *,
    run_id: str | None = None,
    snapshot_date: date | None = None,
    dsns: SourceDsns | None = None,
) -> RunContext:
    return RunContext(
        run_id=run_id or str(uuid.uuid4()),
        profile=profile,
        snapshot_date=snapshot_date or clock.today(profile.site.tz),
        lake_root=lake_root,
        dsns=dsns,
    )
