"""Agent proposals as the application shows them (F12-FR-13): a read-only view of the ``proposal`` table.

The agents service writes proposals; app-api only reads them, so the Insights window and the batch drawer keep
working when the agents service is down. The newest proposal of a row is the one shown.
"""

from collections.abc import Sequence

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_api.models import Proposal


class ProposalRef(BaseModel):
    id: int
    status: str  # pending_approval | rejected_by_validator | approved | rejected | executed
    priority: str | None  # high | normal, from the drafted ticket


def latest_by_row(session: Session, row_keys: Sequence[str]) -> dict[str, ProposalRef]:
    if not row_keys:
        return {}
    rows = session.scalars(select(Proposal).where(Proposal.row_key.in_(list(row_keys))).order_by(Proposal.id))
    return {
        row.row_key: ProposalRef(
            id=row.id, status=row.status, priority=(row.payload_json or {}).get("priority")
        )
        for row in rows
        if row.row_key is not None
    }
