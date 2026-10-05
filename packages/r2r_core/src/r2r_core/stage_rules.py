"""The stage rules: the single definition of how a lot's stage is decided (03-domain-model section 4).

Rules are evaluated top-down and the first match wins. Each condition is SQL over the columns of
``staging.batch_flat`` plus two derived ones (the stage engine also publishes both):

* ``cycle_start_date``: the lot start for a re-evaluation lot, else the goods receipt date (NULL when the
  receipt was netted out by a reversal)
* ``ud_effective``: the usage decision code is an accept code of the profile

The pipeline renders this list into a ``CASE``; the application's Explain view shows it. The profile can
change SLAs, labels and ``applies_if``, but not this logic.
"""

from dataclasses import dataclass

from r2r_core.profile import SiteProfile


@dataclass(frozen=True)
class StageRule:
    id: str
    stage_key: str
    condition_sql: str
    description: str
    inputs: tuple[str, ...]  # the columns the condition reads, all published (Explain shows their values)


RULES: tuple[StageRule, ...] = (
    StageRule(
        "R-REL", "released", "ud_effective", "An accepting usage decision has been posted", ("ud_effective",)
    ),
    StageRule(
        "R-QAR",
        "qa_release",
        "lims_status = 'approved' AND NOT ud_effective",
        "LIMS has approved the lot and no accepting usage decision is posted",
        ("lims_status", "ud_effective"),
    ),
    StageRule(
        "R-QCT",
        "qc_testing",
        "lims_status <> 'approved' AND ((NOT offsite_test AND sample_collected_date IS NOT NULL) "
        "OR (offsite_test AND sample_shipped_date IS NOT NULL))",
        "The sample is being tested (onsite once collected, offsite once shipped); includes a LIMS rejection",
        ("lims_status", "offsite_test", "sample_collected_date", "sample_shipped_date"),
    ),
    StageRule(
        "R-QCS",
        "qc_ship",
        "offsite_test AND sample_collected_date IS NOT NULL AND sample_shipped_date IS NULL",
        "An offsite sample is collected and not yet shipped",
        ("offsite_test", "sample_collected_date", "sample_shipped_date"),
    ),
    StageRule(
        "R-RCP",
        "receipt",
        "cycle_start_date IS NOT NULL AND inbound_check_status IN ('open', 'failed')",
        "The inbound check is open or failed",
        ("cycle_start_date", "inbound_check_status"),
    ),
    StageRule(
        "R-CLO",
        "call_off",
        "cycle_start_date IS NOT NULL AND received_location_type = '3pl' AND transfer_to_site_date IS NULL",
        "Received at a 3PL and not yet transferred to site",
        ("cycle_start_date", "received_location_type", "transfer_to_site_date"),
    ),
    StageRule(
        "R-SMP",
        "sampling",
        "cycle_start_date IS NOT NULL",
        "The cycle has started and no sample is out",
        ("cycle_start_date",),
    ),
    StageRule("R-PND", "pending", "TRUE", "No goods receipt (or it was reversed)", ()),
)


def check_rules(profile: SiteProfile) -> None:
    """Raise ``ValueError`` if a rule names a stage the profile does not have."""
    keys = {stage.key for stage in profile.stages}
    for rule in RULES:
        if rule.stage_key not in keys:
            raise ValueError(
                f"rule {rule.id} needs stage {rule.stage_key!r}, which the profile does not define"
            )
