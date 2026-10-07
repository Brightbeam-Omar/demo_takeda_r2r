"""``make record-agents``: record the model's answers for the demo-start state (F12-FR-03, OQ-139).

It runs the air-gap agent live (``anthropic``) for every candidate of a stack that is in the canonical
demo-start state, writes one recording per model call, and checks each draft with the validator. Nothing is
written to the database: the runs use an in-memory trace and no proposal is stored.

It records into a new folder and replaces ``recordings/air_gap/`` only when **all four** air-gap batches were
recorded and every draft passed V1-V6, so a failed or partial run never destroys working recordings. It
refuses to run when the candidates are not the four rows of the demo-start state.

The API key is read from the environment by the gateway and appears in no output.
"""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from r2r_core import clock
from r2r_core.profile import SiteProfile, load_profile

from agents.air_gap import agent as air_gap_agent
from agents.air_gap.candidates import AGENT_KEY, Candidate, air_gap_rows
from agents.air_gap.schema import AirGapTicket
from agents.air_gap.validator import ValidationContext, validate_ticket
from agents.gateway.anthropic import AnthropicGateway
from agents.gateway.base import GatewayError, ModelGateway
from agents.gateway.replay import RecordingGateway, clear_recordings
from agents.harness.runner import run_agent
from agents.harness.trace import MemoryTrace
from agents.prompts import load_prompt
from agents.settings import Settings
from agents.tools.http import ReadOnlyHttp, ToolError

# The air-gap list at demo start: B5003 (the story batch, 30 h) and the three older ones (datagen
# `quirks.air_gap_ages_hours`; a test keeps the two in step). Worst first, as the Insights window lists them.
DEMO_START_HOURS = (90, 70, 62, 30)


class RecordError(Exception):
    """The recording cannot proceed or did not give four good drafts. The message is safe to print."""


@dataclass
class Recorded:
    candidate: Candidate
    passed: bool
    headline: str | None
    model_calls: int
    tokens_in: int
    tokens_out: int


def _context(http: ReadOnlyHttp, profile: SiteProfile, demo_user: str | None) -> ValidationContext:
    return ValidationContext(
        http=http,
        demo_user=demo_user,
        threshold_hours=profile.air_gap.threshold_hours,
        high_priority_days=profile.agents.air_gap.high_priority_days,
        now=clock.now(),
        today=clock.today(),
    )


def record_all(
    *,
    http: ReadOnlyHttp,
    live: ModelGateway,
    profile: SiteProfile,
    directory: Path,
    demo_user: str | None,
    expected_hours: tuple[int, ...] = DEMO_START_HOURS,
) -> list[Recorded]:
    """Record every candidate into ``directory/.recording`` and move it into place if all of them are good."""
    candidates = air_gap_rows(http, demo_user)
    if tuple(c.air_gap_hours for c in candidates) != expected_hours:
        found = ", ".join(f"{c.batch_no} {c.air_gap_hours} h" for c in candidates) or "none"
        wanted = ", ".join(f"{h} h" for h in expected_hours)
        raise RecordError(
            f"The candidates are not the demo-start air gaps ({wanted}): found {found}. "
            "Run `make demo-reset` first (or `make seed` until F13 exists)."
        )
    staging = directory / ".recording"
    shutil.rmtree(staging, ignore_errors=True)
    recorder = RecordingGateway(live, staging)
    prompt = load_prompt(AGENT_KEY, air_gap_agent.PROMPT_VERSION)
    results: list[Recorded] = []
    for candidate in candidates:
        trace = MemoryTrace()
        spec = air_gap_agent.build_spec(http)
        outcome = run_agent(
            spec,
            recorder,
            trace,
            user_message=prompt.render_user(
                row_key=candidate.row_key,
                batch_no=candidate.batch_no,
                material_no=candidate.material_no,
                air_gap_hours=candidate.air_gap_hours,
                threshold_hours=profile.air_gap.threshold_hours,
                high_priority_days=profile.agents.air_gap.high_priority_days,
                today=clock.today().isoformat(),
            ),
            input_payload={"row_key": candidate.row_key},
            demo_user=demo_user,
        )
        responses = [s for s in trace.steps if s["step_type"] == "model_response"]
        passed: bool = False
        headline: str | None = outcome.message or "no ticket"
        if isinstance(outcome.output, AirGapTicket):
            verdict = validate_ticket(outcome.output, _context(http, profile, demo_user))
            passed, headline = verdict.passed, verdict.headline
        results.append(
            Recorded(
                candidate,
                passed,
                headline,
                len(responses),
                sum(s["tokens_in"] or 0 for s in responses),
                sum(s["tokens_out"] or 0 for s in responses),
            )
        )
    bad = [r for r in results if not r.passed]
    if bad:
        shutil.rmtree(staging, ignore_errors=True)
        detail = "; ".join(f"{r.candidate.batch_no}: {r.headline}" for r in bad)
        raise RecordError(
            f"{len(bad)} draft(s) did not pass the validator ({detail}). Nothing was replaced; run again."
        )
    clear_recordings(directory, AGENT_KEY)
    target = directory / AGENT_KEY
    target.mkdir(parents=True, exist_ok=True)
    for file in sorted((staging / AGENT_KEY).glob("*.json")):
        shutil.move(str(file), target / file.name)
    shutil.rmtree(staging, ignore_errors=True)
    return results


def main() -> int:
    settings = Settings.from_env()
    profile = load_profile(os.environ.get("SITE_PROFILE", "site_a"))
    http = ReadOnlyHttp.from_settings(settings)
    try:
        live = AnthropicGateway(settings.model_id)
        results = record_all(
            http=http,
            live=live,
            profile=profile,
            directory=settings.recordings_dir,
            demo_user=settings.service_user,
        )
    except (RecordError, GatewayError, ToolError) as error:
        print(f"record-agents: {error}", file=sys.stderr)
        return 1
    print(f"record-agents: model {settings.model_id}, recordings in {settings.recordings_dir / AGENT_KEY}")
    for r in results:
        print(
            f"  {r.candidate.batch_no} ({r.candidate.air_gap_hours} h): passed V1-V6, "
            f"{r.model_calls} model calls, {r.tokens_in} tokens in, {r.tokens_out} out"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
