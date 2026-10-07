"""``python -m scenario.cli``: what ``make scenario`` and ``make demo-reset`` run (F13-FR-04).

``run <step>``, ``reset`` and ``list`` call the scenario API, print every progress line as it arrives and exit
non-zero when the step is refused or fails, so a script or the e2e run can rely on the exit code.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable

import httpx

ACTOR = "system"  # OQ-150: runs from the command line are audited as `system`


def base_url() -> str:
    return os.environ.get("SCENARIO_URL", "http://localhost:8100").rstrip("/")


def headers() -> dict[str, str]:
    return {"X-Scenario-Token": os.environ.get("SCENARIO_TOKEN", ""), "X-Actor-User": ACTOR}


def follow(client: httpx.Client, run_id: str, out: Callable[[str], None]) -> bool:
    """Print the lines of a run until it ends. True when it succeeded."""
    ok = False
    with client.stream("GET", f"/scenario/runs/{run_id}/events", headers=headers(), timeout=None) as stream:
        stream.raise_for_status()
        for line in stream.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[len("data: ") :])
            out(f"  {event['message']}")
            if event["kind"] in ("done", "failed"):
                ok = event["kind"] == "done"
    return ok


def start(client: httpx.Client, path: str, out: Callable[[str], None]) -> str | None:
    response = client.post(path, headers=headers())
    if response.status_code == 202:
        run_id: str = response.json()["run_id"]
        return run_id
    detail = response.json().get("detail", response.text) if response.content else response.status_code
    out(f"refused: {detail['message'] if isinstance(detail, dict) else detail}")
    return None


def main(
    argv: list[str] | None = None, out: Callable[[str], None] = print, client: httpx.Client | None = None
) -> int:
    parser = argparse.ArgumentParser(prog="scenario", description="Run a scenario step or reset the demo")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run one step")
    run.add_argument("step")
    commands.add_parser("reset", help="reset the demo to its starting state")
    commands.add_parser("list", help="list the steps and whether their preconditions hold")
    args = parser.parse_args(argv)
    try:
        with client or httpx.Client(base_url=base_url(), timeout=30.0) as http:
            if args.command == "list":
                for step in http.get("/scenario/steps", headers=headers()).raise_for_status().json():
                    out(f"{step['id']:<24} [{step['preconditions']}] {step['title']}")
                return 0
            path = "/scenario/reset" if args.command == "reset" else f"/scenario/steps/{args.step}/run"
            run_id = start(http, path, out)
            return 0 if run_id is not None and follow(http, run_id, out) else 1
    except httpx.HTTPError as error:
        out(f"error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
