"""Shared fixtures: the site_a profile and a RowFacts factory."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from r2r_core.domain import LotType, RowFacts, StageKey
from r2r_core.profile import SiteProfile, load_profile


@pytest.fixture(scope="session")
def profile() -> SiteProfile:
    return load_profile("site_a")


@pytest.fixture
def facts() -> Callable[..., RowFacts]:
    """Build a RowFacts for an onsite, onsite-test, initial-lot row at sampling; override as needed."""

    def build(**overrides: Any) -> RowFacts:
        values: dict[str, Any] = {
            "row_key": "RM10001|B1|10000001",
            "stage_key": StageKey("sampling"),
            "lot_type": LotType.INITIAL,
            "received_location_type": "onsite",
            "offsite": False,
            "current_stage_entry_date": date(2026, 10, 8),
            "system_need_by_locked": None,
            "on_hold": False,
            "ud_rejected": False,
            "lims_status": "none",
            "ud_effective": False,
            "ud_code": None,
            "lims_approved_at": None,
        }
        values.update(overrides)
        return RowFacts(**values)

    return build
