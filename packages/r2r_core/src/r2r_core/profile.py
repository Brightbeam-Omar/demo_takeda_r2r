"""Site profile: Pydantic models for the YAML in 03-domain-model section 2, plus the loader.

Everything that varies by site (stages, SLAs, teams, reason codes, terminology) lives in the profile
(constitution P4). Unknown keys are rejected so a typo fails at startup.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    ValidationError,
    field_validator,
    model_validator,
)

from r2r_core.applies_if import parse_applies_if

PROFILES_ENV = "SITE_PROFILES_DIR"
_RELATIVE_DIR = Path("config") / "site-profiles"


class ProfileError(Exception):
    """The profile is missing or invalid."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Site(_Model):
    code: str
    name: str
    timezone: str

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown timezone {value!r}") from error
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class Demo(_Model):
    start_datetime: datetime
    seed: int

    @field_validator("start_datetime")
    @classmethod
    def _has_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("start_datetime must include a timezone offset")
        return value


class Stage(_Model):
    key: str
    label: str
    sla_days: NonNegativeInt
    team: str
    action: str
    applies_if: str | None = None
    terminal: bool = False
    show_card: bool = True  # F17: a card on the Overview stage strip (still counted in the total)

    @field_validator("applies_if")
    @classmethod
    def _valid_condition(cls, value: str | None) -> str | None:
        if value is not None:
            parse_applies_if(value)
        return value


class UdCodes(_Model):
    accept: list[str]
    reject: list[str]
    cancel: list[str]

    @model_validator(mode="after")
    def _disjoint(self) -> "UdCodes":
        seen: set[str] = set()
        for code in [*self.accept, *self.reject, *self.cancel]:
            if code in seen:
                raise ValueError(f"ud_codes: {code!r} appears in more than one list")
            seen.add(code)
        return self


class Metric(_Model):
    id: str
    label: str
    stage: str | None
    computed_in: Literal["app", "pipeline"]
    tier: int
    sla_days: NonNegativeInt | None = None
    null_reason: str | None = None  # required when computed_in is app


class MetricRag(_Model):
    green_min_pct: int
    amber_min_pct: int

    @model_validator(mode="after")
    def _ordered(self) -> "MetricRag":
        if self.green_min_pct < self.amber_min_pct:
            raise ValueError("metric_rag.green_min_pct must be >= amber_min_pct")
        return self


class RagConfig(_Model):
    amber_days_remaining_lt: NonNegativeInt


class AirGapConfig(_Model):
    threshold_hours: NonNegativeInt


class ReleaseOnCoa(_Model):
    """F18-FR-10: the single release deadline, in days from the cycle start, when Release on COA is set."""

    sla_days: PositiveInt


class Exports(_Model):
    """F18-FR-07: the stage sets of the two queue exports."""

    sampling_plan: list[str] = Field(min_length=1)
    qc_queue: list[str] = Field(min_length=1)


class FullSpecPair(_Model):
    material: str
    supplier: str


class Labelled(_Model):
    """A stable key with a display label (OQ-082). Plain strings in the YAML are normalised to this."""

    key: str
    label: str


def _labelled(values: object) -> object:
    if not isinstance(values, list):
        return values
    return [{"key": i, "label": i.replace("_", " ").title()} if isinstance(i, str) else i for i in values]


class ReasonCode(_Model):
    """F19-FR-06: a need-by reason code with its display label."""

    code: str
    label: str


class StatusOption(_Model):
    """F19-FR-05: a status of the status log, with its dot colour."""

    key: str
    label: str
    colour: Literal["green", "amber", "red"]


class Terms(_Model):
    """UI vocabulary (F15, OQ-075). Every key is optional; derived defaults follow ``erp`` and ``lims``."""

    erp: str = "ERP"
    lims: str = "LIMS"
    qms: str = "QMS"
    qc_lab: str = "QC Lab"
    insights_banner: str = ""
    erp_blocked_tag: str = ""
    planner_overrides: str = "planner overrides"

    @model_validator(mode="before")
    @classmethod
    def _derive_defaults(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        filled = dict(data)
        erp = str(filled.get("erp", "ERP"))
        lims = str(filled.get("lims", "LIMS"))
        filled.setdefault("insights_banner", f"{lims}–{erp} Insights")
        filled.setdefault("erp_blocked_tag", f"{erp} BLOCKED")
        return filled


class Adapters(_Model):
    erp: str


class SiteProfile(_Model):
    site: Site
    demo: Demo
    stages: list[Stage]
    reeval_sla_overrides: dict[str, NonNegativeInt]
    ud_codes: UdCodes
    metrics: list[Metric]
    metric_rag: MetricRag
    rag: RagConfig
    air_gap: AirGapConfig
    molecule_types: Annotated[list[Labelled], BeforeValidator(_labelled)]
    material_classes: Annotated[list[Labelled], BeforeValidator(_labelled)]
    full_spec_pairs: list[FullSpecPair]
    release_on_coa: ReleaseOnCoa
    exports: Exports
    reason_codes: list[ReasonCode] = Field(min_length=1)
    status_options: list[StatusOption] = Field(min_length=1)
    status_reasons: list[Labelled]
    adapters: Adapters
    terms: Terms = Terms()

    @model_validator(mode="after")
    def _cross_checks(self) -> "SiteProfile":
        keys: set[str] = set()
        for stage in self.stages:
            if stage.key in keys:
                raise ValueError(f"duplicate stage key {stage.key!r}")
            keys.add(stage.key)
        terminals = [s.key for s in self.stages if s.terminal]
        if len(terminals) != 1:
            raise ValueError(f"exactly one terminal stage is required (found {len(terminals)})")
        for key in self.reeval_sla_overrides:
            if key not in keys:
                raise ValueError(f"reeval_sla_overrides refers to unknown stage {key!r}")
        for key in (*self.exports.sampling_plan, *self.exports.qc_queue):
            if key not in keys:
                raise ValueError(f"exports refers to unknown stage {key!r}")
        for name, entries in (
            ("reason_codes", [r.code for r in self.reason_codes]),
            ("status_options", [o.key for o in self.status_options]),
            ("status_reasons", [r.key for r in self.status_reasons]),
        ):
            if len(set(entries)) != len(entries):
                raise ValueError(f"duplicate key in {name}")
        metric_ids: set[str] = set()
        for metric in self.metrics:
            if metric.id in metric_ids:
                raise ValueError(f"duplicate metric id {metric.id!r}")
            metric_ids.add(metric.id)
            if metric.computed_in == "app" and not (metric.null_reason or "").strip():
                raise ValueError(f"metric {metric.id} is computed in the app, so it needs a null_reason")
            if metric.stage is None:
                if metric.sla_days is None:
                    raise ValueError(f"metric {metric.id} has no stage, so it needs an explicit sla_days")
            elif metric.stage not in keys:
                raise ValueError(f"metric {metric.id} refers to unknown stage {metric.stage!r}")
        return self

    def stage(self, key: str) -> Stage:
        for stage in self.stages:
            if stage.key == key:
                return stage
        raise KeyError(key)


def profiles_dir(env: dict[str, str] | None = None) -> Path:
    """``SITE_PROFILES_DIR`` if set, else ``config/site-profiles`` found by walking up from this file."""
    value = (os.environ if env is None else env).get(PROFILES_ENV, "").strip()
    if value:
        return Path(value)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / _RELATIVE_DIR
        if candidate.is_dir():
            return candidate
    raise ProfileError(f"cannot find {_RELATIVE_DIR.as_posix()}; set {PROFILES_ENV}")


def parse_profile(data: object) -> SiteProfile:
    try:
        return SiteProfile.model_validate(data)
    except ValidationError as error:
        raise ProfileError(f"invalid site profile:\n{error}") from error


def load_profile(name_or_path: str | Path) -> SiteProfile:
    """Load ``config/site-profiles/<name>.yaml`` by name, or a YAML file by path."""
    text = str(name_or_path)
    is_path = isinstance(name_or_path, Path) or "/" in text or text.endswith((".yaml", ".yml"))
    path = Path(text) if is_path else profiles_dir() / f"{text}.yaml"
    if not path.is_file():
        raise ProfileError(f"site profile not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ProfileError(f"{path} is not valid YAML: {error}") from error
    return parse_profile(data)
