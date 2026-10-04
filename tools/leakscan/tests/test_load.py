"""T1: denylist loading and precedence [F02-FR-02, F02-FR-03, F02-AC-03]."""

from pathlib import Path

import pytest
from leakscan.load import UsageError, is_ci, load_denylist, no_denylist_outcome, parse_denylist


def test_f02_fr02_env_wins_over_file(tmp_path: Path) -> None:
    (tmp_path / ".leakscan").mkdir()
    (tmp_path / ".leakscan" / "denylist.txt").write_text("fromfile\n")
    denylist = load_denylist({"LEAKSCAN_DENYLIST": "fromenv\nsecond"}, tmp_path)
    assert denylist is not None
    assert denylist.origin == "env"
    assert [r.source for r in denylist.rules] == ["fromenv", "second"]


def test_f02_fr02_falls_back_to_file(tmp_path: Path) -> None:
    (tmp_path / ".leakscan").mkdir()
    (tmp_path / ".leakscan" / "denylist.txt").write_text("fromfile\n")
    denylist = load_denylist({}, tmp_path)
    assert denylist is not None
    assert denylist.origin == "file"
    assert [r.source for r in denylist.rules] == ["fromfile"]


@pytest.mark.parametrize("value", ["", "   ", "\n\n", "# only a comment"])
def test_f02_fr02_blank_env_and_empty_lists_count_as_missing(tmp_path: Path, value: str) -> None:
    assert load_denylist({"LEAKSCAN_DENYLIST": value}, tmp_path) is None


def test_f02_fr02_nothing_configured_is_none(tmp_path: Path) -> None:
    assert load_denylist({}, tmp_path) is None


def test_f02_fr03_comments_and_blanks_skipped_and_rules_numbered_from_one() -> None:
    rules = parse_denylist("# header\n\nfirst\n  \n# note\nre:sec+ond\n")
    assert [(r.number, r.source) for r in rules] == [(1, "first"), (2, "re:sec+ond")]


def test_f02_fr03_invalid_regex_is_usage_error() -> None:
    with pytest.raises(UsageError, match="rule #1"):
        parse_denylist("re:(unclosed")


def test_f02_oq010_env_value_that_is_a_file_path_is_usage_error(tmp_path: Path) -> None:
    path = tmp_path / "list.txt"
    path.write_text("x")
    with pytest.raises(UsageError, match="content, not a path"):
        load_denylist({"LEAKSCAN_DENYLIST": str(path)}, tmp_path)


@pytest.mark.parametrize(
    ("value", "expected"), [("true", True), ("TRUE", True), ("1", True), ("false", False), ("", False)]
)
def test_f02_fr02_is_ci(value: str, expected: bool) -> None:
    assert is_ci({"CI": value}) is expected


def test_f02_ac03_ci_without_denylist_exits_1_with_clear_message() -> None:
    code, message = no_denylist_outcome({"CI": "true"})
    assert code == 1
    assert "LEAKSCAN_DENYLIST" in message
    assert "CI" in message


def test_f02_fr02_local_without_denylist_warns_and_exits_0() -> None:
    code, message = no_denylist_outcome({})
    assert code == 0
    assert message.startswith("warning")
