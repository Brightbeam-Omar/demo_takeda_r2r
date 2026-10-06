"""Turns a ``Plan`` into the dated list of event-function calls that replays it (F05-FR-01).

An event names a simulator function (``erp.goods_receipt``) and carries its body as plain values. Numbers the
database allocates (inspection lots, samples, demand lines, deviations) are referenced symbolically as
``@name``: the executor remembers each created key under its ``capture`` name and fills the references in.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from datagen.model import BatchPlan, LotPlan, Plan
from datagen.next_inspection import MANUFACTURE_LEAD

HISTORY_BEFORE_FIRST_EVENT = timedelta(days=1)


@dataclass
class Event:
    day: date
    system: str  # erp | lims | qms
    kind: str  # the event function's name
    body: dict[str, Any]
    capture: str | None = None  # remember the created key under this name
    at: datetime | None = None  # explicit instant (otherwise assigned from the day and the order)
    tags: list[str] = field(default_factory=list)


def lot_ref(lot: LotPlan) -> str:
    return f"@lot:{lot.ref}"


def sample_ref(lot: LotPlan, index: int) -> str:
    return f"@sample:{lot.ref}#{index}"


def po_ref(batch: BatchPlan) -> str:
    return f"@po:{batch.po_ref}"


def _items(lot: LotPlan) -> list[dict[str, str]]:
    return [
        {"check_code": code, "check_label": label, "outcome": outcome}
        for code, label, outcome in lot.check_items
    ]


def _lot_events(batch: BatchPlan, lot: LotPlan) -> list[Event]:
    out: list[Event] = []
    key = {"matnr": batch.matnr, "charg": batch.charg}
    if lot.lot_type == "01":
        out.append(
            Event(
                lot.start,
                "erp",
                "goods_receipt",
                {
                    **key,
                    "lifnr": batch.lifnr,
                    "lgort": batch.lgort,
                    "menge": batch.quantity,
                    "budat": lot.start,
                    "hsdat": lot.start - MANUFACTURE_LEAD,
                    "vfdat": lot.start + timedelta(days=730),
                    "licha": batch.supplier_batch,
                    "qnext": batch.next_inspection,
                    "pastrterm": lot.start,
                    "ebeln": po_ref(batch),
                    "ebelp": "00010",
                    **({"items": _items(lot)} if lot.check == "open" and lot.check_items else {}),
                },
                capture=lot_ref(lot),
            )
        )
        if lot.reversed_same_day:
            out.append(Event(lot.start, "erp", "goods_receipt_reversal", {**key, "budat": lot.start}))
            return out
        if lot.check_done is not None:
            body = {"prueflos": lot_ref(lot), "status": lot.check, "completed_on": lot.check_done}
            if lot.check_items:
                body["items"] = _items(lot)
            out.append(Event(lot.check_done, "erp", "inbound_check", body))
        if lot.transfer is not None:
            body = {**key, "from_lgort": batch.lgort, "to_lgort": batch.site_lgort, "budat": lot.transfer}
            out.append(Event(lot.transfer, "erp", "transfer", body))
    else:
        body = {**key, "pastrterm": lot.start, "inbound_check": lot.check}
        if lot.check_items:
            body["items"] = _items(lot)
        out.append(Event(lot.start, "erp", "reeval_lot", body, capture=lot_ref(lot)))
    for index, sample in enumerate(lot.samples):
        ref = sample_ref(lot, index)
        collected = {
            "inspection_lot_no": lot_ref(lot),
            "material_no": batch.matnr,
            "batch_no": batch.charg,
            "collected_date": sample.collected,
            "offsite_test": sample.offsite,
            "external_lab": sample.lab,
        }
        out.append(Event(sample.collected, "lims", "sample_collected", collected, capture=ref))
        if sample.shipped is not None:
            out.append(
                Event(
                    sample.shipped,
                    "lims",
                    "sample_shipped",
                    {"sample_id": ref, "shipped_date": sample.shipped},
                )
            )
        if sample.started is not None:
            out.append(Event(sample.started, "lims", "testing_started", {"sample_id": ref}))
        for number, test in enumerate(sample.results, start=1):
            day = test.completed_on or sample.closed_on or sample.started or sample.collected
            body = {
                "sample_id": ref,
                "test_code": test.code,
                "test_name": test.name,
                "result_value": test.value,
                "spec": test.spec,
                "status": test.status,
                "completed_on": day,
            }
            out.append(Event(day, "lims", "test_result_recorded", body, tags=[f"result-{number}"]))
        if sample.outcome != "open" and sample.closed_on is not None:
            kind = "approved" if sample.outcome == "approved" else "rejected"
            out.append(Event(sample.closed_on, "lims", kind, {"sample_id": ref}, at=sample.approved_at))
        if sample is lot.latest and lot.results_recorded is not None and sample.closed_on is not None:
            body = {"prueflos": lot_ref(lot), "at": lot.results_recorded}
            out.append(Event(sample.closed_on, "erp", "results_recorded", body, at=lot.results_recorded))
    if lot.ud_code is not None and lot.ud_date is not None:
        body = {"prueflos": lot_ref(lot), "vcode": lot.ud_code, "vdatum": lot.ud_date}
        out.append(Event(lot.ud_date, "erp", "usage_decision", body))
    return out


def batch_events(batch: BatchPlan) -> list[Event]:
    out: list[Event] = []
    key = {"matnr": batch.matnr, "charg": batch.charg}
    for lot in batch.lots:
        out.extend(_lot_events(batch, lot))
    out.extend(Event(day, "erp", "hold", {**key, "hold": on}) for day, on in batch.holds)
    for day, on in batch.blocks:
        out.append(Event(day, "erp", "stock_block" if on else "stock_unblock", dict(key)))
    return out


def plan_events(plan: Plan) -> list[Event]:
    """All events of the plan in replay order: by day, and within a day in the order they were planned."""
    events: list[Event] = []
    for index, demand in enumerate(plan.demands):
        name = f"@demand:{index}"
        body = {
            "matnr": demand.matnr,
            "campaign": demand.campaign,
            "requirement_date": demand.requirement_date,
            "quantity": demand.quantity,
            "is_open": True,
        }
        events.append(Event(demand.created_on, "erp", "demand", body, capture=name))
        if demand.closed_on is not None:
            events.append(Event(demand.closed_on, "erp", "demand", {**body, "id": name, "is_open": False}))
    for line in plan.po_lines:
        body = {
            "matnr": line.matnr,
            "lifnr": line.lifnr,
            "lgort": line.lgort,
            "scheduled_date": line.scheduled,
            "menge": line.quantity,
        }
        events.append(Event(line.created_on, "erp", "po_line_created", body, capture=f"@po:{line.ref}"))
    for batch in plan.batches:
        events.extend(batch_events(batch))
    for number, deviation in enumerate(plan.deviations):
        name = f"@deviation:{number}"
        body = {
            "title": deviation.title,
            "description": deviation.description,
            "severity": deviation.severity,
            "opened_on": deviation.opened_on,
            "root_cause_category": deviation.root_cause_category,
            "causal_factor": deviation.causal_factor,
            "owner": deviation.owner,
            "links": [{"material_no": m, "batch_no": b} for m, b in deviation.links],
        }
        if deviation.closed_on is None:
            body["investigation_summary"] = deviation.investigation_summary
        events.append(Event(deviation.opened_on, "qms", "deviation_opened", body, capture=name))
        if deviation.closed_on is not None:
            body = {
                "deviation_no": name,
                "closed_on": deviation.closed_on,
                "investigation_summary": deviation.investigation_summary,
            }
            events.append(Event(deviation.closed_on, "qms", "deviation_closed", body))
    for number, change in enumerate(plan.change_controls):
        name = f"@cc:{number}"
        body = {
            "title": change.title,
            "current_state": change.current_state,
            "proposed_state": change.proposed_state,
            "status": "open",
            "opened_on": change.opened_on,
            "links": [{"material_no": m, "batch_no": b} for m, b in change.links],
        }
        events.append(Event(change.opened_on, "qms", "change_control_opened", body, capture=name))
        if change.status != "open" and change.status_on is not None:
            body = {"cc_no": name, "status": change.status, "effective_on": change.effective_on}
            events.append(Event(change.status_on, "qms", "change_control_status", body))
    for expedite in plan.expedites:
        body = {
            "matnr": expedite.matnr,
            "charg": expedite.charg,
            "requested_on": expedite.requested_on,
            "due_date": expedite.due_date,
        }
        events.append(Event(expedite.requested_on, "erp", "expedite_requested", body))
    events.sort(key=lambda event: event.day)  # stable: planning order breaks ties within a day
    return events
