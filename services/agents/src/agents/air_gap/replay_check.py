"""Do the demo-start air gaps replay? The check behind ``make doctor`` (F14-FR-05).

Replay keys depend on the whole conversation, tool results included (OQ-139), so the only honest test is
to run the agent for each current candidate against the recordings. It uses an in-memory trace and stores
nothing: no proposal, no trace row, no audit entry. It also says whether the candidates are the four
demo-start rows, since the recordings are valid only for that state.
"""

from dataclasses import dataclass
from pathlib import Path

from r2r_core import clock
from r2r_core.profile import SiteProfile

from agents.air_gap import agent as air_gap_agent
from agents.air_gap.candidates import AGENT_KEY, air_gap_rows
from agents.gateway.base import GatewayError
from agents.gateway.replay import ReplayGateway, ReplayMiss
from agents.harness.runner import run_agent
from agents.harness.trace import MemoryTrace
from agents.prompts import load_prompt
from agents.record import DEMO_START_HOURS
from agents.tools.http import ReadOnlyHttp, ToolError


@dataclass
class CandidateReplay:
    batch_no: str
    air_gap_hours: int
    replays: bool
    missing_key: str | None
    message: str


@dataclass
class ReplayCheck:
    recordings_dir: str
    recording_files: int
    demo_start: bool
    candidates: list[CandidateReplay]


def replay_check(
    http: ReadOnlyHttp,
    profile: SiteProfile,
    directory: Path,
    demo_user: str | None,
    expected_hours: tuple[int, ...] = DEMO_START_HOURS,
) -> ReplayCheck:
    folder = directory / AGENT_KEY
    files = len(list(folder.glob("*.json"))) if folder.is_dir() else 0
    candidates = air_gap_rows(http, demo_user)
    prompt = load_prompt(AGENT_KEY, air_gap_agent.PROMPT_VERSION)
    gateway = ReplayGateway(directory)
    results: list[CandidateReplay] = []
    for candidate in candidates:
        try:
            outcome = run_agent(
                air_gap_agent.build_spec(http),
                gateway,
                MemoryTrace(),
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
            replays, key, message = outcome.status == "submitted", None, outcome.message or "replays"
        except ReplayMiss as miss:
            replays, key, message = False, miss.key, f"no recording for model call {miss.turn}"
        except (GatewayError, ToolError) as error:
            replays, key, message = False, None, str(error)
        results.append(CandidateReplay(candidate.batch_no, candidate.air_gap_hours, replays, key, message))
    return ReplayCheck(
        recordings_dir=str(directory),
        recording_files=files,
        demo_start=tuple(c.air_gap_hours for c in candidates) == expected_hours,
        candidates=results,
    )
