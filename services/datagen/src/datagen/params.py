"""Typed loader for ``params.yaml``: every tuning number of the generator."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

PARAMS_FILE = Path(__file__).with_name("params.yaml")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class History(_Model):
    weeks: int
    metric_weeks: int


class Volumes(_Model):
    materials: int
    suppliers: int
    batches: int
    reeval_batches: int
    reeval_open_share: float
    previous_reevals: dict[int, float]
    deviations: int
    deviation_open_share: float


class Mix(_Model):
    drug_substance_share: float
    molecule_types: dict[str, float]
    threepl_share: float
    offsite_share: float


class StageAge(_Model):
    within_sla: float
    backlog_max_days: int


class Completions(_Model):
    min_per_week: int
    recent_release_per_week: tuple[int, int]
    early_release_per_week: tuple[int, int]


class OnTime(_Model):
    weekly_min: float
    weekly_max: float
    default: float
    last_week: dict[str, tuple[float, float]] = {}  # stage key -> (min, max) for the last metric week only


class Durations(_Model):
    on_time_centre: float
    sigma: float
    late_centre: float
    late_sigma: float


class Demand(_Model):
    need_by_max_days: int
    no_demand_share: float
    extra_rows: dict[int, float]
    closed_history_share: float
    stale_open_share: float


class DeviationParams(_Model):
    severity: dict[str, float]
    links: dict[int, float]
    open_on_qa_release: int


class Quirks(_Model):
    failed_inbound_checks: int
    rejected_uds: int
    on_hold_batches: int
    released_holds: int
    erp_blocked_batches: int
    air_gap_lots: int
    quantities: list[int]


class Params(_Model):
    history: History
    volumes: Volumes
    mix: Mix
    open_stage_mix: dict[str, float]
    stage_tolerance_pp: float
    rag_mix: dict[str, float]
    rag_tolerance_pp: float
    stage_age: dict[str, StageAge]
    completions: Completions
    on_time: OnTime
    durations: Durations
    demand: Demand
    deviations: DeviationParams
    quirks: Quirks

    @model_validator(mode="after")
    def _shares_add_up(self) -> "Params":
        groups: dict[str, dict[str, float] | dict[int, float]] = {
            "open_stage_mix": self.open_stage_mix,
            "rag_mix": self.rag_mix,
            "molecule_types": self.mix.molecule_types,
            "previous_reevals": self.volumes.previous_reevals,
            "extra_rows": self.demand.extra_rows,
            "severity": self.deviations.severity,
            "links": self.deviations.links,
        }
        for name, shares in groups.items():
            total = sum(shares.values())
            if abs(total - 1.0) > 1e-9:
                raise ValueError(f"{name} must add up to 1 (got {total})")
        if set(self.stage_age) != set(self.open_stage_mix):
            raise ValueError("stage_age needs exactly the stages of open_stage_mix")
        return self


def load_params(path: Path | None = None) -> Params:
    with (path or PARAMS_FILE).open(encoding="utf-8") as handle:
        return Params.model_validate(yaml.safe_load(handle))
