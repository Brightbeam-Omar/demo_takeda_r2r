"""The evidence-field registry (F12-FR-06, OQ-140): the only things a ticket may cite, fixed in code.

Each system has one kind of record and a few fields. ``ref`` is the record's id; ``field`` is a key of the
stable projection the tool returns for that record (``agents.tools.sources``), so the validator can read the
same record again and compare. A value that is null in the source is written ``none``.

| system | ref (record)                | fields                           |
|--------|-----------------------------|----------------------------------|
| LIMS   | sample id (`S-0000404`)     | `status`, `approved_at`          |
| ERP    | inspection lot (`10000459`) | `ud_code`, `results_recorded_at` |
| QMS    | deviation number            | `status`                         |

Required in every ticket: the LIMS `approved_at` and an ERP lot item (normally `results_recorded_at`).
"""

from datetime import UTC, datetime
from typing import Any, Protocol

NONE = "none"

EVIDENCE_FIELDS: dict[str, frozenset[str]] = {
    "LIMS": frozenset({"status", "approved_at"}),
    "ERP": frozenset({"ud_code", "results_recorded_at"}),
    "QMS": frozenset({"status"}),
}


class _Item(Protocol):
    @property
    def system(self) -> str: ...
    @property
    def field(self) -> str: ...


def is_lims_approval(item: _Item) -> bool:
    return item.system == "LIMS" and item.field == "approved_at"


def is_erp_lot_item(item: _Item) -> bool:
    return item.system == "ERP" and item.field in EVIDENCE_FIELDS["ERP"]


def parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def normalise(value: Any) -> str:
    """Compare values as text: null is ``none``, timestamps are UTC to the second (formatting is no fault)."""
    if value is None:
        return NONE
    text = str(value).strip()
    parsed = parse_timestamp(text) if text[:1].isdigit() and "T" in text else None
    if parsed is not None:
        return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return text
