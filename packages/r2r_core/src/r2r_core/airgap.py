"""Air-gap detection: LIMS approved, but the result never transferred to the ERP (03 section 6)."""

import datetime as dt


def air_gap(
    lims_status: str,
    ud_code: str | None,
    lims_approved_at: dt.datetime | None,
    now: dt.datetime,
    threshold_hours: int,
    erp_results_recorded_at: dt.datetime | None = None,
) -> tuple[bool, int]:
    """Return ``(is_air_gap, hours)``.

    ``hours`` is the whole hours since LIMS approval (0 when the lot is not approved, has no approval
    time, or the approval is in the future). It is an air gap only when the lot is approved, there is no
    usage decision of any kind (``ud_code IS NULL``), the ERP has no record of the results
    (``erp_results_recorded_at IS NULL``), and at least ``threshold_hours`` have passed.
    Rejected lots are never air gaps. Both datetimes must be timezone-aware.
    """
    if lims_status != "approved" or lims_approved_at is None:
        return False, 0
    elapsed = max(now - lims_approved_at, dt.timedelta(0))
    hours = int(elapsed.total_seconds() // 3600)
    return ud_code is None and erp_results_recorded_at is None and elapsed >= dt.timedelta(
        hours=threshold_hours
    ), hours
