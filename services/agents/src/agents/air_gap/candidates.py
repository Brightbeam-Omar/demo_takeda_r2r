"""Candidates: the rows that are air gaps now and have no open proposal (the flow's first step).

Detection is deterministic and not the agent's job: app-api already flags ``air_gap`` at read time (F03). The
Insights endpoint lists exactly those rows, worst first, so the agent works the same list the screen shows.
"""

from dataclasses import dataclass

from sqlalchemy import Engine, select

from agents.db import proposal
from agents.tools.http import ReadOnlyHttp

AGENT_KEY = "air_gap"
KIND = "airgap_ticket"
OPEN_STATUSES = ("pending_approval", "approved", "executed")


@dataclass(frozen=True)
class Candidate:
    row_key: str
    batch_no: str
    material_no: str
    air_gap_hours: int


def air_gap_rows(http: ReadOnlyHttp, demo_user: str | None) -> list[Candidate]:
    body = http.get_json("app", "/api/overview/insights", demo_user=demo_user)
    return [
        Candidate(r["row_key"], r["batch_no"], r["material_no"], int(r["air_gap_hours"]))
        for r in body["rows"]
    ]


def row_keys_with_proposals(engine: Engine, *, open_only: bool) -> set[str]:
    """Rows that have a proposal: an open one, or any (autorun skips rows that were ever proposed, OQ-137)."""
    query = select(proposal.c.row_key).where(proposal.c.agent_key == AGENT_KEY, proposal.c.kind == KIND)
    if open_only:
        query = query.where(proposal.c.status.in_(OPEN_STATUSES))
    with engine.connect() as connection:
        return {row for (row,) in connection.execute(query) if row is not None}
