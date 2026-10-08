"""F14-FR-05 / AC-05: every doctor check passes on a healthy stack and fails with its fix when it should."""

import json
from pathlib import Path

from doctor.checks import RECREATE_AGENTS, Result, run_all
from doctor.system import Reply, System

GIB = 1024**3


class FakeSystem(System):
    """A machine with a healthy stack; a test breaks one thing at a time."""

    def __init__(self) -> None:
        super().__init__(Path("."), {})
        self.docker_bytes = 16 * GIB
        self.files = {".env": "x", ".leakscan/denylist.txt": "term"}
        self.up = True
        self.busy: set[int] = set()
        self.recordings = 12
        self.replay: dict[str, object] = {
            "recordings_dir": "/recordings",
            "recording_files": 12,
            "demo_start": True,
            "candidates": [
                {"batch_no": b, "air_gap_hours": h, "replays": True, "missing_key": None, "message": "ok"}
                for b, h in [("B1", 90), ("B2", 70), ("B3", 62), ("B5003", 30)]
            ],
        }
        self.http: dict[str, int] = {}

    def run(self, command: list[str], timeout: float = 20) -> tuple[int, str]:
        if command[:2] == ["docker", "info"]:
            return 0, str(self.docker_bytes)
        if command[:3] == ["docker", "compose", "ps"]:
            ports = [
                {"PublishedPort": p} for p in (5432, 8100, 8101, 8102, 8103, 8200, 3001, 8000, 5173, 8080)
            ]
            return 0, json.dumps({"Service": "x", "Publishers": ports}) if self.up else ""
        if command[:3] == ["docker", "compose", "exec"]:
            return 0, str(self.recordings)
        return 1, ""

    def get(self, url: str, headers: dict[str, str] | None = None, timeout: float = 30) -> Reply:
        if url.endswith("/replay-check"):
            return Reply(200, json.dumps(self.replay))
        return Reply(self.http.get(url, 200), "{}")

    def port_in_use(self, port: int) -> bool:
        return port in self.busy or (
            self.up and port in (5432, 8100, 8101, 8102, 8103, 8200, 3001, 8000, 5173, 8080)
        )

    def exists(self, relative: str) -> bool:
        return relative in self.files

    def text(self, relative: str) -> str:
        return self.files.get(relative, "")


def failed(results: list[Result]) -> dict[str, Result]:
    return {r.name: r for r in results if r.status == "fail"}


def test_f14_fr05_a_healthy_stack_passes_every_check() -> None:
    results = run_all(FakeSystem(), expect_up=False)
    assert failed(results) == {} and all(r.status == "ok" for r in results)
    assert any("4 of 4 air gaps replay" in r.detail for r in results)


def test_f14_ac05_an_empty_recordings_mount_fails_and_prints_the_recreate_command() -> None:
    system = FakeSystem()
    system.recordings = 0
    [bad] = failed(run_all(system, expect_up=False)).values()
    assert bad.name == "Agents container: /recordings is not empty"
    assert bad.fix == RECREATE_AGENTS == "docker compose up -d --force-recreate agents"


def test_f14_fr05_a_missing_replay_key_names_the_batch_and_the_fix() -> None:
    system = FakeSystem()
    system.replay["candidates"][3].update(
        replays=False, missing_key="k" * 64, message="no recording for model call 2"
    )  # type: ignore[index]
    [bad] = failed(run_all(system, expect_up=False)).values()
    assert "3 of 4 replay" in bad.detail and "B5003" in bad.detail
    assert RECREATE_AGENTS in bad.fix and "make record-agents" in bad.fix


def test_f14_fr05_a_state_that_is_not_demo_start_says_to_reset() -> None:
    system = FakeSystem()
    system.replay["demo_start"] = False
    [bad] = failed(run_all(system, expect_up=False)).values()
    assert bad.fix == "make demo-reset"


def test_f14_fr05_low_docker_memory_missing_env_and_denylist_each_fail_with_a_fix() -> None:
    system = FakeSystem()
    system.docker_bytes = 8 * GIB
    system.files = {}
    bad = failed(run_all(system, expect_up=False))
    assert set(bad) == {"Docker memory", ".env is present", "Leak denylist is present"}
    assert "12 GB" in bad["Docker memory"].fix and bad[".env is present"].fix == "cp .env.example .env"


def test_f14_fr05_a_port_held_by_something_else_fails_but_our_own_containers_pass() -> None:
    system = FakeSystem()
    system.up = False
    system.busy = {8080}
    results = run_all(system, expect_up=False)
    assert set(failed(results)) == {"Port 8080 (frontend (present from here))"}


def test_f14_fr05_a_stopped_stack_skips_its_checks_unless_it_is_expected_up() -> None:
    system = FakeSystem()
    system.up = False
    assert failed(run_all(system, expect_up=False)) == {}
    assert any(r.status == "skip" for r in run_all(system, expect_up=False))
    assert failed(run_all(system, expect_up=True))["The stack is running"].fix == "make up"


def test_f14_fr05_an_unhealthy_endpoint_fails() -> None:
    system = FakeSystem()
    system.http = {"http://localhost:3001/server_info": 0}
    assert set(failed(run_all(system, expect_up=False))) == {"Dagster health"}
