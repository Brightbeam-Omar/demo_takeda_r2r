"""T2: text scanning, masking and line numbers [F02-FR-03, F02-FR-05, F02-AC-01]."""

from pathlib import Path

from leakscan.load import parse_denylist
from leakscan.scan import Finding, mask, scan_file, scan_text


def test_f02_ac01_case_insensitive_hit_is_masked_with_line_number(tmp_path: Path) -> None:
    """F02-AC-01: 'FooBarCo plant' with denylist 'foobarco' is found and printed masked."""
    target = tmp_path / "notes.txt"
    target.write_text("first line\nFooBarCo plant\n")
    [finding] = scan_file(target, "notes.txt", parse_denylist("foobarco"))
    assert finding.render() == "notes.txt:2: F*** (rule #1)"
    assert "oobarco" not in finding.render().lower()


def test_f02_fr05_mask_is_first_character_plus_stars() -> None:
    assert mask("FooBarCo") == "F***"
    assert mask("@client.example") == "@***"


def test_f02_fr03_plain_terms_do_not_match_inside_longer_words() -> None:
    rules = parse_denylist("acme")
    assert scan_text("acme, ACME. (acme)", rules)
    assert scan_text("acmecorp xacme acme2", rules) == []


def test_f02_fr03_hyphens_at_signs_and_dots_work_as_term_characters() -> None:
    rules = parse_denylist("acme-real-client\nclient.example\nsite.a")
    text = "see Acme-Real-Client\nmail pat@client.example today\nsite.a is fine\nsiteXa is not"
    assert [(h.location, h.rule) for h in scan_text(text, rules)] == [("1", 1), ("2", 2), ("3", 3)]


def test_f02_fr03_regex_entries_are_used_as_written_without_boundaries() -> None:
    rules = parse_denylist("re:secret.ite")
    [hit] = scan_text("a SecretSite b\nnothing", rules)
    assert hit.matched == "SecretSite"
    assert scan_text("xsecretsitey", rules)  # no added boundaries


def test_f02_fr03_rule_number_follows_non_comment_order() -> None:
    rules = parse_denylist("# c\nalpha\n\nbeta")
    assert [h.rule for h in scan_text("beta alpha", rules)] == [1, 2]


def test_f02_fr05_every_occurrence_on_a_line_is_reported() -> None:
    assert len(scan_text("alpha and alpha", parse_denylist("alpha"))) == 2


def test_f02_fr03_empty_regex_matches_are_ignored() -> None:
    assert scan_text("anything", parse_denylist("re:x*")) == []


def test_f02_fr05_finding_render_for_non_line_locations() -> None:
    finding = Finding("book.xlsx", "Sheet1!B2", "Acme", 3)
    assert finding.render() == "book.xlsx:Sheet1!B2: A*** (rule #3)"


def test_f02_fr01_undecodable_bytes_do_not_crash(tmp_path: Path) -> None:
    target = tmp_path / "latin.txt"
    target.write_bytes(b"caf\xe9 acme\n")
    [finding] = scan_file(target, "latin.txt", parse_denylist("acme"))
    assert finding.location == "1"
