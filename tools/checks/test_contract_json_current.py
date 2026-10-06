"""Repo guard: ``specs/contract.json`` is what ``tools/contract_schema.py`` generates [F21-FR-06, F21-AC-06].

CI runs this through ``make check``, so a change to a published schema, to 04-data-contracts or to the
descriptions without a regenerated file fails the build. Regenerate with
``uv run python tools/contract_schema.py``.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parents[1] / "contract_schema.py"


def load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("contract_schema", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f21_ac06_the_committed_contract_json_is_current() -> None:
    tool = load_tool()
    assert tool.OUTPUT.read_text(encoding="utf-8") == tool.render(), (
        "specs/contract.json is stale. Run: make contract-json"
    )


def test_f21_ac06_check_fails_when_the_file_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = load_tool()
    stale = tmp_path / "contract.json"
    data = json.loads(tool.render())
    data["objects"][0]["columns"].pop()  # a column the pipeline publishes is missing
    stale.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(tool, "OUTPUT", stale)
    assert tool.main(["--check"]) == 1
    assert tool.main([]) == 0  # regenerating repairs it
    assert tool.main(["--check"]) == 0


def test_f21_ac06_every_published_object_and_column_is_listed_with_a_type_and_description() -> None:
    from r2r_pipeline.contract_schemas import published_schemas
    from r2r_pipeline.publish import PUBLISH_ORDER

    tool = load_tool()
    contract = json.loads(tool.OUTPUT.read_text(encoding="utf-8"))
    assert [o["name"] for o in contract["objects"]] == list(PUBLISH_ORDER)
    for obj in contract["objects"]:
        declared = [field.name for field in published_schemas()[obj["name"]]]
        assert [c["name"] for c in obj["columns"]] == declared
        assert obj["description"] and obj["grain"]
        assert all(c["type"] and c["description"] for c in obj["columns"]), obj["name"]


def test_f21_ac06_the_generator_stops_on_a_column_nobody_described(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = load_tool()
    bare = tmp_path / "descriptions.yaml"
    bare.write_text("objects: {}\ncolumns: {_common: {}}\n", encoding="utf-8")
    monkeypatch.setattr(tool, "DESCRIPTIONS", bare)
    with pytest.raises(tool.ContractError, match="no entry for object"):
        tool.build()
