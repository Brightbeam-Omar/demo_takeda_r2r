"""T1: site profile models, loader and validation [F03-FR-01, F03-FR-02, F03-AC-13]."""

import copy
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from r2r_core.profile import ProfileError, SiteProfile, load_profile, profiles_dir

REPO_ROOT = Path(__file__).resolve().parents[3]
SITE_A = REPO_ROOT / "config" / "site-profiles" / "site_a.yaml"


def _raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(SITE_A.read_text())
    return copy.deepcopy(data)


def _write(tmp_path: Path, data: dict[str, Any], name: str = "p.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
    return path


def test_f03_fr02_site_a_matches_the_domain_model_yaml_exactly() -> None:
    """F03-FR-02: site_a.yaml is the YAML block of 03-domain-model section 2."""
    text = (REPO_ROOT / "specs" / "03-domain-model.md").read_text()
    block = re.search(r"```yaml\n(.*?)```", text, re.S)
    assert block is not None
    assert yaml.safe_load(block.group(1)) == yaml.safe_load(SITE_A.read_text())


def test_f03_fr01_site_a_loads_with_the_domain_model_values() -> None:
    profile = load_profile("site_a")
    assert [s.key for s in profile.stages] == [
        "pending", "receipt", "call_off", "sampling", "qc_ship", "qc_testing", "qa_release", "released",
    ]  # fmt: skip
    assert profile.stage("qc_testing").sla_days == 42
    assert profile.reeval_sla_overrides == {"call_off": 5, "sampling": 5, "qc_testing": 27, "qa_release": 3}
    assert [s.key for s in profile.stages if s.terminal] == ["released"]
    assert profile.rag.amber_days_remaining_lt == 3
    assert profile.air_gap.threshold_hours == 24
    assert profile.metric_rag.green_min_pct == 90
    assert len(profile.reason_codes) == 9
    assert profile.site.timezone == "Europe/Dublin"
    assert profile.demo.start_datetime.utcoffset() is not None
    m5 = next(m for m in profile.metrics if m.id == "M5")
    assert (m5.stage, m5.sla_days) == (None, 30)


def test_f03_fr01_load_by_path_and_by_name_in_a_custom_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(tmp_path, _raw(), "custom.yaml")
    assert isinstance(load_profile(path), SiteProfile)
    assert isinstance(load_profile(str(path)), SiteProfile)
    monkeypatch.setenv("SITE_PROFILES_DIR", str(tmp_path))
    assert profiles_dir() == tmp_path
    assert isinstance(load_profile("custom"), SiteProfile)


def test_f03_fr01_default_directory_is_found_by_walking_up_from_the_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SITE_PROFILES_DIR", raising=False)
    assert profiles_dir() == REPO_ROOT / "config" / "site-profiles"


def test_f03_fr01_missing_profile_is_a_profile_error(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="not found"):
        load_profile(tmp_path / "nope.yaml")


def test_f03_ac13_duplicate_stage_key_raises_profile_error_naming_the_key(tmp_path: Path) -> None:
    """F03-AC-13: an invalid profile (duplicate stage key) raises ProfileError naming the key."""
    data = _raw()
    data["stages"].append(dict(data["stages"][1]))  # a second 'receipt'
    with pytest.raises(ProfileError, match="receipt"):
        load_profile(_write(tmp_path, data))


def _mutate_no_terminal(d: dict[str, Any]) -> None:
    d["stages"][-1]["terminal"] = False


def _mutate_two_terminals(d: dict[str, Any]) -> None:
    d["stages"][0]["terminal"] = True


def _mutate_metric_unknown_stage(d: dict[str, Any]) -> None:
    d["metrics"][0]["stage"] = "nowhere"


def _mutate_metric_null_stage_without_sla(d: dict[str, Any]) -> None:
    d["metrics"][4].pop("sla_days")


def _mutate_reeval_unknown_key(d: dict[str, Any]) -> None:
    d["reeval_sla_overrides"]["nowhere"] = 3


def _mutate_empty_reason_codes(d: dict[str, Any]) -> None:
    d["reason_codes"] = []


def _mutate_unknown_key(d: dict[str, Any]) -> None:
    d["surprise"] = 1


def _mutate_bad_timezone(d: dict[str, Any]) -> None:
    d["site"]["timezone"] = "Mars/Base"


def _mutate_duplicate_metric(d: dict[str, Any]) -> None:
    d["metrics"][1]["id"] = "M1"


def _mutate_ud_overlap(d: dict[str, Any]) -> None:
    d["ud_codes"]["reject"].append("A")


def _mutate_rag_order(d: dict[str, Any]) -> None:
    d["metric_rag"] = {"green_min_pct": 70, "amber_min_pct": 80}


def _mutate_naive_start(d: dict[str, Any]) -> None:
    d["demo"]["start_datetime"] = "2026-10-12T08:00:00"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_mutate_no_terminal, "exactly one terminal"),
        (_mutate_two_terminals, "exactly one terminal"),
        (_mutate_metric_unknown_stage, "nowhere"),
        (_mutate_metric_null_stage_without_sla, "M5"),
        (_mutate_reeval_unknown_key, "nowhere"),
        (_mutate_empty_reason_codes, "reason_codes"),
        (_mutate_unknown_key, "surprise"),
        (_mutate_bad_timezone, "Mars/Base"),
        (_mutate_duplicate_metric, "M1"),
        (_mutate_ud_overlap, "A"),
        (_mutate_rag_order, "green_min_pct"),
        (_mutate_naive_start, "timezone"),
    ],
)
def test_f03_fr01_invalid_profiles_are_rejected(tmp_path: Path, mutate: Any, message: str) -> None:
    data = _raw()
    mutate(data)
    with pytest.raises(ProfileError, match=message):
        load_profile(_write(tmp_path, data))


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("mystery == 'x'", "mystery"),  # unknown field fails at load time (OQ-017)
        ("received_location_type", "boolean"),  # bare name must be a boolean field
        ("offsite_test == 'yes'", "string"),  # == is for string fields
        ("received_location_type = '3pl'", "applies_if"),  # unsupported syntax
        ("__import__('os')", "applies_if"),
    ],
)
def test_f03_fr01_applies_if_is_validated_at_load_time(tmp_path: Path, expression: str, message: str) -> None:
    data = _raw()
    data["stages"][2]["applies_if"] = expression
    with pytest.raises(ProfileError, match=message):
        load_profile(_write(tmp_path, data))
