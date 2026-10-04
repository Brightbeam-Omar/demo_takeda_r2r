"""T4: hashed allow-list [F02-FR-08, F02-AC-04]."""

import hashlib
from pathlib import Path

import pytest
from leakscan.allow import allow_hash, apply_allowlist, load_allowlist, parse_allowlist
from leakscan.load import UsageError, parse_denylist
from leakscan.scan import scan_file

RULES = parse_denylist("foobarco\nre:site\\s?a")


def _hash(term: str) -> str:
    return hashlib.sha256(term.lower().encode()).hexdigest()


def test_f02_fr08_hash_is_sha256_of_lowercased_matched_text() -> None:
    assert allow_hash("FooBarCo") == _hash("foobarco")
    assert len(allow_hash("x")) == 64


def test_f02_ac04_allowed_path_and_term_is_ignored(tmp_path: Path) -> None:
    """F02-AC-04: an allow-list hash for a path/term ignores that occurrence."""
    target = tmp_path / "docs" / "note.txt"
    target.parent.mkdir()
    target.write_text("FooBarCo\n")
    findings = scan_file(target, "docs/note.txt", RULES)
    allow = parse_allowlist(f"docs/note.txt:{_hash('foobarco')}\n")
    assert len(findings) == 1
    assert apply_allowlist(findings, allow) == []


def test_f02_fr08_entry_is_specific_to_the_path() -> None:
    allow = parse_allowlist(f"a/one.txt:{_hash('foobarco')}")
    from leakscan.scan import Finding

    other = Finding("a/two.txt", "1", "FooBarCo", 1)
    assert apply_allowlist([other], allow) == [other]


def test_f02_fr08_entry_is_specific_to_the_term() -> None:
    from leakscan.scan import Finding

    allow = parse_allowlist(f"a/one.txt:{_hash('foobarco')}")
    other = Finding("a/one.txt", "1", "Site A", 2)
    assert apply_allowlist([other], allow) == [other]


def test_f02_oq015_works_for_regex_rules_via_the_matched_text() -> None:
    from leakscan.scan import Finding

    allow = parse_allowlist(f"a.txt:{_hash('site a')}")
    assert apply_allowlist([Finding("a.txt", "3", "Site A", 2)], allow) == []


def test_f02_oq015_comments_blank_lines_and_no_globs() -> None:
    from leakscan.scan import Finding

    allow = parse_allowlist(f"# why\n\ndocs/*:{_hash('foobarco')}\n")
    assert apply_allowlist([Finding("docs/x.txt", "1", "foobarco", 1)], allow) != []  # '*' is literal


@pytest.mark.parametrize("line", ["nocolon", "path:nothex", "path:" + "A" * 64, ":" + "a" * 64])
def test_f02_fr08_malformed_entries_are_usage_errors(line: str) -> None:
    with pytest.raises(UsageError, match="allow"):
        parse_allowlist(line)


def test_f02_fr08_load_reads_leakscan_allow_txt_and_tolerates_absence(tmp_path: Path) -> None:
    assert load_allowlist(tmp_path) == frozenset()
    (tmp_path / ".leakscan").mkdir()
    (tmp_path / ".leakscan" / "allow.txt").write_text(f"x.txt:{_hash('foobarco')}\n")
    assert load_allowlist(tmp_path) == {("x.txt", _hash("foobarco"))}
