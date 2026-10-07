"""One function per check. Each returns a ``Result``; a failing one carries the command that fixes it."""

import json
from dataclasses import dataclass
from typing import Literal

from doctor.system import System

Status = Literal["ok", "fail", "skip"]

# Docker Desktop reports less than the slider says (VM overhead): a 12 GB setting shows about 11.7 GiB.
MIN_DOCKER_GIB = 11.5
GIB = 1024**3
RECREATE_AGENTS = "docker compose up -d --force-recreate agents"

# Host ports the stack publishes: (compose variable, default, what it is).
PORTS: list[tuple[str, int, str]] = [
    ("POSTGRES_HOST_PORT", 5432, "Postgres"),
    ("SCENARIO_HOST_PORT", 8100, "scenario service"),
    ("ERP_HOST_PORT", 8101, "ERP simulator"),
    ("LIMS_HOST_PORT", 8102, "LIMS simulator"),
    ("QMS_HOST_PORT", 8103, "QMS simulator"),
    ("AGENTS_HOST_PORT", 8200, "agents service"),
    ("DAGSTER_HOST_PORT", 3001, "Dagster"),
    ("APP_API_HOST_PORT", 8000, "app API"),
    ("FRONTEND_HOST_PORT", 5173, "frontend dev server"),
    ("FRONTEND_WEB_HOST_PORT", 8080, "frontend (present from here)"),
]


@dataclass
class Result:
    name: str
    status: Status
    detail: str
    fix: str = ""


def ok(name: str, detail: str) -> Result:
    return Result(name, "ok", detail)


def fail(name: str, detail: str, fix: str) -> Result:
    return Result(name, "fail", detail, fix)


def skip(name: str, detail: str) -> Result:
    return Result(name, "skip", detail)


def port_of(system: System, variable: str, default: int) -> int:
    value = system.env.get(variable, "")
    return int(value) if value.isdigit() else default


def _docker_bytes(system: System) -> int | None:
    code, out = system.run(["docker", "info", "--format", "{{.MemTotal}}"])
    return int(out.strip()) if code == 0 and out.strip().isdigit() else None


def docker_running(system: System) -> Result:
    if _docker_bytes(system) is None:
        return fail(
            "Docker is running",
            "the Docker daemon does not answer",
            "Start Docker Desktop and wait until it says it is running.",
        )
    return ok("Docker is running", "the daemon answers")


def docker_memory(system: System) -> Result:
    total = _docker_bytes(system)
    if total is None:
        return skip("Docker memory", "Docker is not running")
    gib = total / GIB
    if gib < MIN_DOCKER_GIB:
        return fail(
            "Docker memory",
            f"{gib:.1f} GiB is available to Docker; the demo needs 12 GB (accepts {MIN_DOCKER_GIB}+ GiB)",
            "Docker Desktop > Settings > Resources > Memory: set 12 GB or more, then Apply & restart.",
        )
    return ok("Docker memory", f"{gib:.1f} GiB available to Docker")


def env_file(system: System) -> Result:
    if system.exists(".env"):
        return ok(".env is present", ".env")
    return fail(".env is present", "there is no .env", "cp .env.example .env")


def denylist(system: System) -> Result:
    if system.env.get("LEAKSCAN_DENYLIST", "").strip() or system.text(".leakscan/denylist.txt").strip():
        return ok("Leak denylist is present", "the leak scanner has its list")
    return fail(
        "Leak denylist is present",
        "no .leakscan/denylist.txt and no LEAKSCAN_DENYLIST",
        "cp .leakscan/denylist.example.txt .leakscan/denylist.txt, then fill in the client terms "
        "(tools/leakscan/README.md).",
    )


def published_ports(system: System) -> tuple[bool, set[int]]:
    """Whether any container of this compose project exists, and the host ports they publish."""
    code, out = system.run(["docker", "compose", "ps", "--format", "json"])
    if code != 0:
        return False, set()
    rows = system.json_lines(out)
    ports: set[int] = set()
    for row in rows:
        publishers = row.get("Publishers")
        if not isinstance(publishers, list):
            continue
        for publisher in publishers:
            published = publisher.get("PublishedPort") if isinstance(publisher, dict) else None
            if isinstance(published, int) and published:
                ports.add(published)
    return bool(rows), ports


def ports_free(system: System, ours: set[int]) -> list[Result]:
    results: list[Result] = []
    for variable, default, label in PORTS:
        port = port_of(system, variable, default)
        name = f"Port {port} ({label})"
        if not system.port_in_use(port):
            results.append(ok(name, "free"))
        elif port in ours:
            results.append(ok(name, "in use by this stack"))
        else:
            _, holder = system.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fc"])
            who = next((line[1:] for line in holder.splitlines() if line.startswith("c")), "another program")
            fix = f"Stop {who}, or set {variable} to another port in .env."
            results.append(fail(name, f"held by {who}", fix))
    return results


def health(system: System, name: str, url: str, fix: str) -> Result:
    reply = system.get(url, timeout=5)
    if reply.code == 200:
        return ok(name, f"{url} answers")
    return fail(name, f"{url} gave {reply.code or 'no answer'}", fix)


def recordings_mount(system: System) -> Result:
    name = "Agents container: /recordings is not empty"
    listing = "ls /recordings/air_gap 2>/dev/null | wc -l"
    code, out = system.run(["docker", "compose", "exec", "-T", "agents", "sh", "-c", listing])
    if code != 0:
        return fail(name, "the agents container does not answer", f"make up   (or: {RECREATE_AGENTS})")
    count = int(out.strip()) if out.strip().isdigit() else 0
    if count == 0:
        return fail(
            name,
            "the mount is empty, so the agent could not replay ('No recording for key' on screen)",
            RECREATE_AGENTS,
        )
    return ok(name, f"{count} recording files visible in the container")


def replay_keys(system: System, agents_port: int) -> Result:
    name = "Replay keys exist for the 4 demo-start air gaps"
    url = f"http://localhost:{agents_port}/agents/air_gap/replay-check"
    reply = system.get(url, {"X-Demo-User": "admin"}, timeout=60)
    if reply.code != 200:
        got = reply.code or "no answer"
        return fail(name, f"the agents service gave {got}", "make up   (rebuilds the agents service)")
    body = json.loads(reply.body)
    candidates = body["candidates"]
    if not body["demo_start"]:
        found = ", ".join(f"{c['batch_no']} {c['air_gap_hours']} h" for c in candidates) or "none"
        return fail(name, f"not the demo-start state (air gaps now: {found})", "make demo-reset")
    missing = [c for c in candidates if not c["replays"]]
    if missing:
        detail = "; ".join(f"{c['batch_no']}: {c['message']}" for c in missing)
        return fail(
            name,
            f"{len(candidates) - len(missing)} of {len(candidates)} replay ({detail})",
            f"{RECREATE_AGENTS}   then, if this still fails: make record-agents",
        )
    total = len(candidates)
    return ok(name, f"{total} of {total} air gaps replay ({body['recording_files']} recording files)")


def run_all(system: System, *, expect_up: bool) -> list[Result]:
    results = [docker_running(system), docker_memory(system), env_file(system), denylist(system)]
    up, ours = published_ports(system)
    results.extend(ports_free(system, ours))
    if not up:
        if expect_up:
            results.append(fail("The stack is running", "the stack is not running", "make up"))
        else:
            results.append(
                skip(
                    "Stack checks (health, recordings, replay)",
                    "the stack is not running: run `make up`, then `make doctor` again",
                )
            )
        return results
    app = port_of(system, "APP_API_HOST_PORT", 8000)
    dagster = port_of(system, "DAGSTER_HOST_PORT", 3001)
    web = port_of(system, "FRONTEND_WEB_HOST_PORT", 8080)
    agents = port_of(system, "AGENTS_HOST_PORT", 8200)
    results.extend(
        [
            health(
                system,
                "App health",
                f"http://localhost:{app}/api/health",
                "docker compose up -d app-api   (logs: docker compose logs app-api)",
            ),
            health(
                system,
                "Dagster health",
                f"http://localhost:{dagster}/server_info",
                "docker compose up -d dagster-web dagster-daemon",
            ),
            health(
                system,
                "Frontend on the present-from port",
                f"http://localhost:{web}/api/health",
                "docker compose up -d frontend-web",
            ),
            recordings_mount(system),
            replay_keys(system, agents),
        ]
    )
    return results
