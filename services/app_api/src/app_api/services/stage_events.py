"""What starts and stops each stage, in words, for the SLA Configuration page (F21-FR-06, OQ-134).

The stage rules of 03-domain-model section 4 are fixed in code (the profile changes only SLAs, labels and
``applies_if``), so the entry and exit events of a stage are too. Keyed by stage key; a metric that is not
bound to a stage (the external test metric) has none.
"""

STAGE_EVENTS: dict[str, tuple[str, str]] = {
    "receipt": ("Goods receipt (lot start for a re-evaluation)", "Inbound check completed"),
    "call_off": ("Inbound check completed", "Transferred from the 3PL to site"),
    "sampling": ("Transferred to site (3PL) or inbound check completed", "Sample collected"),
    "qc_ship": ("Sample collected", "Sample shipped to the external lab"),
    "qc_testing": ("Sample collected (onsite) or shipped (offsite)", "LIMS approval"),
    "qa_release": ("LIMS approval", "Usage decision posted"),
}

PIPELINE_WINDOW = "Weekly (ISO week)"
APP_WINDOW = "Tier 2"


def metric_events(stage_key: str | None) -> tuple[str | None, str | None]:
    entry, exit_ = STAGE_EVENTS.get(stage_key or "", (None, None))
    return entry, exit_


def metric_window(computed_in: str) -> str:
    return PIPELINE_WINDOW if computed_in == "pipeline" else APP_WINDOW
