"""T1: params file and seeded streams (F05-FR-02, FR-03, FR-09)."""

import pytest
from datagen.cli import build_parser
from datagen.params import Params, load_params
from datagen.rng import stream
from pydantic import ValidationError


def test_f05_fr03_params_load_and_stage_mix_is_the_decided_one() -> None:
    params = load_params()
    assert params.open_stage_mix == {
        "pending": 0.03,
        "receipt": 0.08,
        "call_off": 0.12,
        "sampling": 0.18,
        "qc_ship": 0.03,
        "qc_testing": 0.42,
        "qa_release": 0.14,
    }
    assert params.rag_mix == {"green": 0.55, "amber": 0.25, "red": 0.20}
    assert params.stage_tolerance_pp == 3
    assert params.completions.min_per_week == 10


def test_f05_params_reject_shares_that_do_not_add_up() -> None:
    data = load_params().model_dump()
    data["rag_mix"] = {"green": 0.9, "amber": 0.25, "red": 0.20}
    with pytest.raises(ValidationError, match="rag_mix"):
        Params.model_validate(data)


def test_f05_fr09_streams_are_reproducible_and_independent() -> None:
    first = [stream(4242, "world").random() for _ in range(3)]
    again = [stream(4242, "world").random() for _ in range(3)]
    other = [stream(4242, "timeline").random() for _ in range(3)]
    assert first == again
    assert first != other
    assert first != [stream(4243, "world").random() for _ in range(3)]


def test_f05_cli_has_both_commands() -> None:
    parser = build_parser()
    assert parser.parse_args(["generate"]).profile == "site_a"
    assert parser.parse_args(["legacy-workbook"]).out.name == "legacy_tracker.xlsx"
