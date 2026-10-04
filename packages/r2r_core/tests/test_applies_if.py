"""T1: the safe `applies_if` mini-evaluator (OQ-017): no eval, two forms only."""

from dataclasses import dataclass

import pytest
from r2r_core.applies_if import parse_applies_if


@dataclass
class Facts:
    received_location_type: str = "onsite"
    offsite: bool = False


def test_f03_oq017_string_equality_form() -> None:
    cond = parse_applies_if("received_location_type == '3pl'")
    assert cond.evaluate(Facts(received_location_type="3pl")) is True
    assert cond.evaluate(Facts()) is False


def test_f03_oq017_bare_boolean_form_with_offsite_test_alias() -> None:
    cond = parse_applies_if("offsite_test")
    assert cond.evaluate(Facts(offsite=True)) is True
    assert cond.evaluate(Facts(offsite=False)) is False


@pytest.mark.parametrize("bad", ["", "a b", "x == 3", "x = 'y'", "'a' == x", "f()", "x == 'a' and y"])
def test_f03_oq017_anything_else_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="applies_if"):
        parse_applies_if(bad)
