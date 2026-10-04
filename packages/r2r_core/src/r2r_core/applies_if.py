"""Safe mini-evaluator for a stage's ``applies_if`` condition (OQ-017).

Two forms only, checked against fixed field lists, never ``eval``:

* ``<string field> == '<literal>'``, for example ``received_location_type == '3pl'``
* ``<boolean field>``, for example ``offsite_test`` (an alias of ``RowFacts.offsite``)
"""

import re
from dataclasses import dataclass

STRING_FIELDS = frozenset({"received_location_type", "lot_type", "lims_status", "ud_code", "stage_key"})
BOOLEAN_FIELDS = frozenset({"offsite", "on_hold", "ud_rejected", "ud_effective"})
ALIASES = {"offsite_test": "offsite"}  # published column name -> RowFacts field

_EQUALS = re.compile(r"\s*([A-Za-z_]\w*)\s*==\s*'([^']*)'\s*")
_BARE = re.compile(r"\s*([A-Za-z_]\w*)\s*")


@dataclass(frozen=True)
class Condition:
    field: str  # the RowFacts attribute to read (aliases already resolved)
    literal: str | None  # None means a bare boolean field

    def evaluate(self, facts: object) -> bool:
        value = getattr(facts, self.field)
        return bool(value) if self.literal is None else bool(value == self.literal)


def parse_applies_if(expression: str) -> Condition:
    """Parse and validate an ``applies_if`` string. Raises ``ValueError`` mentioning ``applies_if``."""
    equals = _EQUALS.fullmatch(expression)
    bare = _BARE.fullmatch(expression)
    if equals is not None:
        name = equals.group(1)
    elif bare is not None:
        name = bare.group(1)
    else:
        raise ValueError(
            f"applies_if {expression!r} must be \"<field> == '<literal>'\" or a bare boolean field name"
        )
    field = ALIASES.get(name, name)
    if field not in STRING_FIELDS | BOOLEAN_FIELDS:
        raise ValueError(f"applies_if uses unknown field {name!r}")
    if equals is not None:
        if field not in STRING_FIELDS:
            raise ValueError(f"applies_if '==' needs a string field, but {name!r} is boolean")
        return Condition(field, equals.group(2))
    if field not in BOOLEAN_FIELDS:
        raise ValueError(f"applies_if bare name {name!r} must be a boolean field")
    return Condition(field, None)
