"""QMS event functions (F04-FR-05). Same conventions as the ERP and LIMS: one transaction per event,
``updated_at`` from ``r2r_core.clock.now()`` through the session, dates defaulting to the demo's today.
"""

from typing import Any

from r2r_core import clock
from r2r_core.db import allocate_number, row_dict
from r2r_core.errors import Conflict, Invalid
from sqlalchemy import select
from sqlalchemy.orm import Session

from qms_sim import schemas
from qms_sim.models import Counter, Deviation, DeviationLink


def links_of(session: Session, deviation_no: str) -> list[DeviationLink]:
    query = select(DeviationLink).where(DeviationLink.deviation_no == deviation_no)
    return list(session.scalars(query.order_by(DeviationLink.material_no, DeviationLink.batch_no)))


def deviation_opened(session: Session, body: schemas.DeviationOpenedIn) -> dict[str, Any]:
    """Open a deviation and link it to the given batches."""
    pairs = [(link.material_no, link.batch_no) for link in body.links]
    if len(set(pairs)) != len(pairs):
        raise Invalid("links contain the same batch twice")

    def taken(number: str) -> bool:
        return session.get(Deviation, number) is not None

    if body.deviation_no is not None:
        if taken(body.deviation_no):
            raise Conflict(f"deviation {body.deviation_no} already exists")
        number = body.deviation_no
    else:
        number = allocate_number(session, Counter, "deviation", lambda n: f"DEV-{n:06d}", exists=taken)
    deviation = Deviation(
        deviation_no=number,
        title=body.title,
        description=body.description,
        severity=body.severity,
        status="open",
        opened_on=body.opened_on or clock.today(),
        closed_on=None,
        root_cause_category=body.root_cause_category,
        owner=body.owner,
    )
    session.add(deviation)
    session.flush()
    session.add_all(DeviationLink(deviation_no=number, material_no=m, batch_no=b) for m, b in pairs)
    session.flush()
    return {"deviation": row_dict(deviation), "links": [row_dict(link) for link in links_of(session, number)]}


def deviation_closed(session: Session, body: schemas.DeviationClosedIn) -> dict[str, Any]:
    deviation = session.get(Deviation, body.deviation_no)
    if deviation is None:
        raise Invalid(f"unknown deviation {body.deviation_no}")
    if deviation.status == "closed":
        raise Invalid(f"deviation {body.deviation_no} is already closed")
    deviation.status = "closed"
    deviation.closed_on = body.closed_on or clock.today()
    session.flush()
    links = [row_dict(link) for link in links_of(session, body.deviation_no)]
    return {"deviation": row_dict(deviation), "links": links}
