"""T4: the order and the failure handling of the demo reset [F13-FR-05, F13-AC-01]. No database, no network."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fakes import FakeDagster, World
from r2r_core.profile import load_profile
from scenario import reset as reset_module
from scenario.reset import Reset
from scenario.runner import Busy, Run, RunRegistry


class Setup:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.world = World()
        self.timeline = self.world.timeline
        self.dagster = FakeDagster(timeline=self.timeline)
        self.world.follow = self.dagster
        self.commands: list[list[str]] = []
        self.exit_code = 0
        self.registry = RunRegistry()

        @contextmanager
        def lock(engine: Any) -> Iterator[None]:
            self.timeline.append("lock taken")
            try:
                yield
            finally:
                self.timeline.append("lock released")

        monkeypatch.setattr(reset_module, "hold_sync_lock", lock)
        monkeypatch.setattr(
            reset_module, "clear_app_tables", lambda engine: self.timeline.append("tables cleared")
        )
        monkeypatch.setattr(
            reset_module, "seed_after_reset", lambda engine, profile: self.timeline.append("clock reset")
        )
        self.reset = Reset(
            engine=None,  # type: ignore[arg-type]
            profile=load_profile("site_a"),
            gateway=self.world.gateway(),
            dagster=lambda: self.dagster,
            registry=self.registry,
            run_command=self.run_command,
            sleep=lambda seconds: None,
        )

    def run_command(self, command: list[str]) -> tuple[int, str]:
        self.commands.append(command)
        self.timeline.append("datagen")
        return self.exit_code, "datagen: 400 batches, 700 lots"

    def run(self, actor: str = "admin") -> Run:
        return self.reset.start(actor, wait=True)


@pytest.fixture
def setup(monkeypatch: pytest.MonkeyPatch) -> Setup:
    monkeypatch.setenv("SCENARIO_TOKEN", "s3cret")
    return Setup(monkeypatch)


def test_f13_fr05_the_reset_runs_its_phases_in_the_specified_order(setup: Setup) -> None:
    run = setup.run()
    assert run.status == "succeeded"
    assert setup.timeline == [
        "POST /agents/autorun/pause",
        "lock taken",
        "tables cleared",
        "clock reset",
        "dagster r2r_reset_lakehouse",
        "datagen",
        "dagster r2r_pipeline",
        "lock released",
        "GET /api/sync/status",
        "POST /agents/autorun/resume",
        "GET /api/overview",
        "GET /proposals",
    ]


def test_f13_fr05_the_sync_lock_is_released_before_waiting_for_the_sync(setup: Setup) -> None:
    """The worker can only mirror the new data once the lock is gone, so waiting inside it would never end."""
    setup.run()
    assert setup.timeline.index("lock released") < setup.timeline.index("GET /api/sync/status")


def test_f13_fr05_datagen_runs_with_the_profile_seed_and_site(setup: Setup) -> None:
    setup.run()
    (command,) = setup.commands
    assert command[1:4] == ["-m", "datagen", "generate"]
    assert command[command.index("--profile") + 1] == "site_a"
    assert "--seed" not in command  # the profile's own seed (F05)


def test_f13_fr05_the_run_ends_with_a_health_summary(setup: Setup) -> None:
    run = setup.run()
    summary = run.events[-1]["message"]
    assert "4 rows" in summary and "1 air gap" in summary and "0 proposals" in summary


def test_f13_fr05_a_failing_datagen_fails_the_reset_and_still_lets_everything_go(setup: Setup) -> None:
    setup.exit_code = 2
    run = setup.run()
    assert run.status == "failed"
    assert "datagen failed" in run.events[-1]["message"]
    assert "dagster r2r_pipeline" not in setup.timeline  # nothing after the failure
    assert "lock released" in setup.timeline  # the worker is not left blocked
    assert "POST /agents/autorun/resume" in setup.timeline  # nor the autorun left paused


def test_f13_fr05_a_failed_pipeline_run_fails_the_reset(setup: Setup) -> None:
    setup.dagster.final = "FAILURE"
    run = setup.run()
    assert run.status == "failed" and "ended FAILURE" in run.events[-1]["message"]
    assert "lock released" in setup.timeline


def test_f13_fr05_an_unreachable_agents_service_is_a_warning_not_a_failure(setup: Setup) -> None:
    setup.world.fail["/agents/autorun/pause"] = 503
    setup.world.fail["/agents/autorun/resume"] = 503
    run = setup.run()
    assert run.status == "succeeded"
    assert any("autorun" in event["message"] and event["kind"] == "line" for event in run.events)


def test_f13_fr05_a_sync_that_never_arrives_fails_the_reset_with_the_reason(setup: Setup) -> None:
    setup.world.synced = False
    run = setup.run()
    assert run.status == "failed" and "did not sync" in run.events[-1]["message"]
    assert "POST /agents/autorun/resume" in setup.timeline


def test_f13_fr05_only_one_run_at_a_time(setup: Setup) -> None:
    setup.registry.begin("step", "advance-day", "admin")
    with pytest.raises(Busy):
        setup.reset.start("admin")


def test_f13_fr05_reset_is_idempotent_so_two_in_a_row_both_succeed(setup: Setup) -> None:
    assert setup.run().status == "succeeded"
    assert setup.run().status == "succeeded"
