"""Deviation details and change controls for the plan (F19-FR-03, OQ-108, OQ-109).

Every ordinary deviation gets a causal factor; closed ones (and about half of the open major ones) get an
investigation summary. About 40 change controls are linked to about 15% of the batches, never to a story
batch, and at least one of them to a batch with no deviation (a green batch that still shows a change). Story
deviations draw nothing: they are the same whatever the seed. Both parts use their own streams, so nothing
planned before is reshuffled. The deviation severity mix is the ``severity`` weights in ``params.yaml``.
"""

from datetime import timedelta

from datagen.model import ChangeControlPlan, Plan, weekdays_between
from datagen.rng import stream

DETAILS_STREAM = "deviation_details"
CHANGES_STREAM = "change_controls"
CHANGE_COUNT = 40
LINKED_BATCH_SHARE = 0.15
OPEN_MAJOR_SUMMARY_SHARE = 0.5
HISTORY_DAYS = 100

CAUSAL_FACTORS = (
    "Carrier handling",
    "Supplier process change",
    "Storage conditions",
    "Documentation error",
    "Equipment calibration",
    "Operator error",
    "Packaging integrity",
    "Method variability",
)
SUMMARIES = (
    "The investigation traced the event to {factor}. The batch was assessed and no further action is needed.",
    "Root cause confirmed as {factor}. A preventive action was agreed with the owner.",
    "The investigation points to {factor}; impact on the batch is assessed as limited.",
    "Review of the records shows {factor}. The supplier was informed and the batch kept under observation.",
)
CHANGES = (
    ("Update the storage specification", "Store at 2-8 C", "Store at 2-25 C"),
    ("Revise the sampling plan", "Sample 3 containers per delivery", "Sample 5 containers per delivery"),
    ("Change the supplier packaging", "Double-bagged drum", "Triple-laminate bag in drum"),
    ("Extend the retest interval", "Retest every 12 months", "Retest every 24 months"),
    ("Add an identity test", "Identity by IR only", "Identity by IR and HPLC"),
    ("Update the label format", "Label template v3", "Label template v4"),
)
STATUSES = ("open", "approved", "closed", "cancelled")
STATUS_WEIGHTS = (0.3, 0.3, 0.3, 0.1)


def plan_quality_data(plan: Plan) -> None:
    _deviation_details(plan)
    _change_controls(plan)


def _deviation_details(plan: Plan) -> None:
    rng = stream(plan.seed, DETAILS_STREAM)
    for deviation in plan.deviations:
        if deviation.story_id:
            continue
        deviation.causal_factor = rng.choice(CAUSAL_FACTORS)
        summary = rng.choice(SUMMARIES).format(factor=deviation.causal_factor.lower())
        wanted = deviation.closed_on is not None or (
            deviation.severity == "major" and rng.random() < OPEN_MAJOR_SUMMARY_SHARE
        )
        deviation.investigation_summary = summary if wanted else None


def _change_controls(plan: Plan) -> None:
    rng = stream(plan.seed, CHANGES_STREAM)
    cal = plan.calendar
    with_deviation = {link for d in plan.deviations for link in d.links}
    eligible = [
        (b.matnr, b.charg)
        for b in plan.batches
        if not b.story_id and b.first_day < cal.last_day - timedelta(days=5)
    ]
    wanted = round(LINKED_BATCH_SHARE * len(plan.batches))
    linked = rng.sample(eligible, min(wanted, len(eligible)))
    if all(link in with_deviation for link in linked):  # at least one change on a batch with no deviation
        linked[0] = next(link for link in eligible if link not in with_deviation)
    rng.shuffle(linked)
    statuses = list(STATUSES) + rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=CHANGE_COUNT - len(STATUSES))
    rng.shuffle(statuses)
    floor = cal.snap_back(cal.last_day - timedelta(days=HISTORY_DAYS))
    ceiling = cal.last_day - timedelta(days=4)
    base, extra = divmod(len(linked), CHANGE_COUNT)
    start = 0
    for number in range(CHANGE_COUNT):
        size = base + (1 if number < extra else 0)
        links = linked[start : start + size]
        start += size
        title, current, proposed = rng.choice(CHANGES)
        opened = rng.choice(weekdays_between(floor, ceiling))
        status = statuses[number]
        status_on = effective = None
        if status != "open":
            later = weekdays_between(
                opened + timedelta(days=1), min(cal.last_day, opened + timedelta(days=30))
            )
            status_on = rng.choice(later)
            if status in ("approved", "closed"):
                effective = status_on + timedelta(days=rng.randint(1, 45))
        plan.change_controls.append(
            ChangeControlPlan(title, current, proposed, opened, status, status_on, effective, links)
        )
