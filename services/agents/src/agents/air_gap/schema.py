"""``AirGapTicket``: what the model returns as the input of its final ``submit_ticket`` call (F12-FR-06)."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from agents.air_gap.evidence import is_erp_lot_item, is_lims_approval

System = Literal["ERP", "LIMS", "QMS"]
Action = Literal["post_usage_decision", "investigate_deviation_first", "check_interface"]


class EvidenceItem(BaseModel):
    system: System
    ref: str = Field(
        description="The record id: sample id (LIMS), inspection lot number (ERP), deviation number (QMS)."
    )
    field: str = Field(description="The field read, from the fixed list in the instructions.")
    value: str = Field(description="The value exactly as a tool returned it; the text 'none' for null.")


class AirGapTicket(BaseModel):
    row_key: str
    title: str = Field(max_length=90)
    summary: str = Field(max_length=600)
    evidence: list[EvidenceItem] = Field(min_length=2)
    hours_in_gap: int
    open_deviations: list[str]
    recommended_action: Action
    priority: Literal["high", "normal"]
    recipient_role: Literal["qa_release"]

    @model_validator(mode="after")
    def _required_evidence(self) -> Self:
        if not any(is_lims_approval(item) for item in self.evidence):
            raise ValueError("evidence must include the LIMS approval (system LIMS, field approved_at)")
        if not any(is_erp_lot_item(item) for item in self.evidence):
            raise ValueError("evidence must include an ERP inspection lot item (system ERP)")
        return self
