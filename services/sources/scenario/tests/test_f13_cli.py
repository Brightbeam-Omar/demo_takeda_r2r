"""T5: `make scenario` and `make demo-reset` call this CLI: progress lines out, exit code for the result [F13-FR-04]."""

import pytest
from fakes import Harness
from fastapi import FastAPI
from fastapi.testclient import TestClient
from scenario.api import build_router
from scenario.cli import main


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> tuple[Harness, TestClient, list[str]]:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    harness = Harness(monkeypatch)
    app = FastAPI()
    app.include_router(build_router(harness.runner, harness.registry))
    return harness, TestClient(app), []


def test_f13_fr04_a_step_prints_its_progress_and_exits_zero(
    cli: tuple[Harness, TestClient, list[str]],
) -> None:
    _, client, lines = cli
    assert main(["run", "run-pipeline"], out=lines.append, client=client) == 0
    assert "  [1/2] Run the pipeline" in lines
    assert lines[-1] == "  run-pipeline finished"


def test_f13_fr04_a_refused_step_prints_the_reason_and_exits_non_zero(
    cli: tuple[Harness, TestClient, list[str]],
) -> None:
    harness, client, lines = cli
    harness.world.rows["B1042"]["stage_key"] = "qa_release"
    assert main(["run", "lims-approve-B1042"], out=lines.append, client=client) == 1
    assert lines == [
        "refused: B1042 is not in QC Testing, so it has already been approved in LIMS. Reset the demo to run this step again."
    ]


def test_f13_fr04_a_failing_step_exits_non_zero(cli: tuple[Harness, TestClient, list[str]]) -> None:
    harness, client, lines = cli
    harness.dagster.final = "FAILURE"
    assert main(["run", "run-pipeline"], out=lines.append, client=client) == 1
    assert "failed" in lines[-1]


def test_f13_fr04_an_unknown_step_exits_non_zero(cli: tuple[Harness, TestClient, list[str]]) -> None:
    _, client, lines = cli
    assert main(["run", "nope"], out=lines.append, client=client) == 1
    assert "unknown step nope" in lines[0]


def test_f13_fr04_list_shows_every_step_with_its_precondition_state(
    cli: tuple[Harness, TestClient, list[str]],
) -> None:
    harness, client, lines = cli
    harness.world.rows["B5003"]["air_gap"] = False
    assert main(["list"], out=lines.append, client=client) == 0
    assert any(line.startswith("lims-approve-B1042") and "[met]" in line for line in lines)
    assert any(line.startswith("ud-post-B5003") and "[unmet]" in line for line in lines)
