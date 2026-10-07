"""F12 T4: the read-only tool registry and its stable projections [F12-FR-04, OQ-139, OQ-140]."""

import json
from typing import Any

import pytest
from agent_support import ROW_KEY, source_transport
from agents.settings import Settings
from agents.tools.http import NotFound, ReadOnlyHttp, ToolError
from agents.tools.registry import read_only_tools
from agents.tools.sources import fetch_deviation


def _http(**kwargs: Any) -> ReadOnlyHttp:
    return ReadOnlyHttp.from_settings(Settings.from_env({}), transport=source_transport(**kwargs))


def _call(name: str, arguments: dict[str, Any], **kwargs: Any) -> tuple[Any, bool]:
    output = read_only_tools(_http(**kwargs)).call(name, arguments, "alex")
    return json.loads(output.content), output.is_error


def test_f12_fr04_five_json_schema_tools_across_four_systems() -> None:
    registry = read_only_tools(_http())
    assert registry.names() == [
        "get_row",
        "get_lims_sample",
        "get_lims_results",
        "get_erp_lot",
        "list_deviations",
    ]
    assert {registry.system_of(n) for n in registry.names()} == {"app", "LIMS", "ERP", "QMS"}
    for spec in registry.specs():
        assert spec.input_schema["type"] == "object" and spec.input_schema["required"]
        assert spec.description


def test_f12_fr04_get_row_returns_only_the_stable_fields() -> None:
    row, is_error = _call("get_row", {"row_key": ROW_KEY})
    assert not is_error
    assert row["batch_no"] == "B5003" and row["air_gap_hours"] == 30 and row["sample_id"] == "S-0000404"
    assert row["lims_approved_at"] == "2026-10-11T01:00:00Z" and row["erp_results_recorded_at"] is None
    text = json.dumps(row)
    for volatile in ("freshness", "mirrored_at", "contract_run_id", "latest_status", "free text"):
        assert volatile not in text


def test_f12_oq139_two_reads_differing_only_in_volatile_fields_give_identical_text() -> None:
    registry_a = read_only_tools(_http(volatile="a"))
    registry_b = read_only_tools(_http(volatile="b"))
    calls = [
        ("get_row", {"row_key": ROW_KEY}),
        ("get_lims_sample", {"sample_id": "S-0000404"}),
        ("get_erp_lot", {"prueflos": "10000459"}),
    ]
    for name, arguments in calls:
        assert (
            registry_a.call(name, arguments, "alex").content
            == registry_b.call(name, arguments, "alex").content
        )


def test_f12_fr04_lims_erp_and_qms_tools() -> None:
    sample, _ = _call("get_lims_sample", {"sample_id": "S-0000404"})
    assert (sample["status"], sample["approved_at"]) == ("approved", "2026-10-11T01:00:00Z")
    assert "updated_at" not in sample
    assert _call("get_lims_results", {"sample_id": "S-0000404"}) == ([], False)
    lot, _ = _call("get_erp_lot", {"prueflos": "10000459"})
    assert (lot["ud_code"], lot["results_recorded_at"]) == (None, None)
    deviation = {
        "deviation_no": "DEV-000039", "title": "Temperature excursion", "severity": "minor", "status": "open",
        "opened_on": "2026-09-01", "closed_on": None, "links": [{"batch_no": "B5003"}],
    }  # fmt: skip
    listed, _ = _call("list_deviations", {"batch_no": "B5003"}, deviations=[deviation])
    assert listed == [{k: v for k, v in deviation.items() if k != "links"}]


def test_f12_fr04_bad_calls_come_back_as_errors_not_exceptions() -> None:
    assert _call("get_row", {})[1] and _call("get_row", {"row_key": 5})[1]
    assert _call("get_row", {"row_key": ROW_KEY, "extra": "x"})[1]
    assert _call("delete_everything", {"x": "y"})[1]
    body, is_error = _call("get_erp_lot", {"prueflos": "99999999"})
    assert is_error and "no record" in body["error"]


def test_f12_fr04_tools_only_ever_issue_get_requests_to_allow_listed_hosts() -> None:
    http = _http()  # the transport raises on any non-GET request
    with pytest.raises(ToolError, match="unknown system"):
        http.get_json("shell", "/x")
    assert not any(hasattr(http, name) for name in ("post", "put", "patch", "delete", "request"))
    with pytest.raises(NotFound):
        fetch_deviation(http, "DEV-999999")
