"""T5: CLI behaviour, exit codes, file selection and commit scanning [F02-FR-01, F02-FR-02, F02-AC-03]."""

import subprocess
from pathlib import Path

import pytest
from leakscan.allow import allow_hash
from leakscan.cli import main

DENY = {"LEAKSCAN_DENYLIST": "foobarco"}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test User", "-c", "user.email=test@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "tracked.txt").write_text("FooBarCo here\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


def test_f02_ac01_finding_is_printed_masked_and_exit_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.txt").write_text("FooBarCo plant\n")
    assert main(["."], DENY, tmp_path) == 1
    out = capsys.readouterr().out
    assert "a.txt:1: F*** (rule #1)" in out
    assert "oobarco" not in out.lower()


def test_f02_fr01_clean_scan_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a.txt").write_text("nothing to see\n")
    assert main(["."], DENY, tmp_path) == 0
    assert "clean" in capsys.readouterr().out


def test_f02_ac03_ci_without_denylist_exits_1_with_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F02-AC-03: CI=true and no denylist gives exit 1 and a clear message."""
    assert main(["."], {"CI": "true"}, tmp_path) == 1
    assert "LEAKSCAN_DENYLIST" in capsys.readouterr().err


def test_f02_fr02_local_without_denylist_warns_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["."], {}, tmp_path) == 0
    assert capsys.readouterr().err.startswith("warning")


def test_f02_fr02_reads_gitignored_file_when_env_is_unset(tmp_path: Path) -> None:
    (tmp_path / ".leakscan").mkdir()
    (tmp_path / ".leakscan" / "denylist.txt").write_text("foobarco\n")
    (tmp_path / "a.txt").write_text("FooBarCo\n")
    assert main(["a.txt"], {}, tmp_path) == 1


def test_f02_fr01_leakscan_directory_is_never_scanned(tmp_path: Path) -> None:
    (tmp_path / ".leakscan").mkdir()
    (tmp_path / ".leakscan" / "denylist.txt").write_text("foobarco\n")
    (tmp_path / ".leakscan" / "denylist.example.txt").write_text("foobarco\n")
    assert main(["."], {}, tmp_path) == 0


def test_f02_oq016_explicit_paths_are_scanned_recursively_without_git(tmp_path: Path) -> None:
    (tmp_path / "deep" / "er").mkdir(parents=True)
    (tmp_path / "deep" / "er" / "x.csv").write_text("a,FooBarCo\n")
    assert main(["deep"], DENY, tmp_path) == 1


def test_f02_oq016_explicit_paths_limit_the_scan(tmp_path: Path) -> None:
    (tmp_path / "bad.txt").write_text("FooBarCo\n")
    (tmp_path / "good.txt").write_text("fine\n")
    assert main(["good.txt"], DENY, tmp_path) == 0


def test_f02_oq014_default_set_covers_tracked_staged_and_untracked_but_not_ignored(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "staged.txt").write_text("FooBarCo\n")
    _git(repo, "add", "staged.txt")
    (repo / "untracked.txt").write_text("FooBarCo\n")
    (repo / "ignored.txt").write_text("FooBarCo\n")
    assert main([], DENY, repo) == 1
    hit_files = {line.split(":")[0] for line in capsys.readouterr().out.splitlines() if "(rule" in line}
    assert hit_files == {"tracked.txt", "staged.txt", "untracked.txt"}


def test_f02_oq014_deleted_tracked_files_do_not_crash(repo: Path) -> None:
    (repo / "tracked.txt").unlink()
    assert main([], DENY, repo) == 0


def test_f02_oq014_file_paths_are_scanned_too(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "foobarco-notes.txt").write_text("clean\n")
    assert main(["."], DENY, tmp_path) == 1
    assert "(path)" in capsys.readouterr().out


def test_f02_oq014_binaries_are_listed_in_summary_and_do_not_fail(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "scan.pdf").write_bytes(b"%PDF\x00\x01")
    assert main(["."], DENY, tmp_path) == 0
    assert "skipped 1 binary files" in capsys.readouterr().out


def test_f02_fr08_allow_list_entry_suppresses_a_finding(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("FooBarCo\n")
    (tmp_path / ".leakscan").mkdir()
    (tmp_path / ".leakscan" / "allow.txt").write_text(f"a.txt:{allow_hash('foobarco')}\n")
    assert main(["."], DENY, tmp_path) == 0


def test_f02_oq010_env_value_that_is_a_path_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "list.txt").write_text("foobarco\n")
    assert main(["."], {"LEAKSCAN_DENYLIST": str(tmp_path / "list.txt")}, tmp_path) == 2
    assert "content, not a path" in capsys.readouterr().err


def test_f02_usage_errors_exit_2(tmp_path: Path) -> None:
    assert main(["missing-dir"], DENY, tmp_path) == 2
    assert main(["."], {"LEAKSCAN_DENYLIST": "re:(bad"}, tmp_path) == 2


def test_f02_oq014_commits_scans_messages_and_author_names(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "b.txt").write_text("clean\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fix FooBarCo thing")
    assert main(["--commits", "HEAD~1..HEAD"], DENY, repo) == 1
    out = capsys.readouterr().out
    assert ":2: F*** (rule #1)" not in out  # message is a single line
    assert ":1: F*** (rule #1)" in out
    assert out.startswith("commits/")


def test_f02_oq014_commits_scans_author_names(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "c.txt").write_text("clean\n")
    _git(repo, "add", "-A")
    subprocess.run(
        ["git", "-c", "user.name=Pat FooBarCo", "-c", "user.email=p@x.invalid", "commit", "-q", "-m", "x"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    assert main(["--commits", "HEAD~1..HEAD"], DENY, repo) == 1
    assert ":author: F*** (rule #1)" in capsys.readouterr().out


def test_f02_oq014_clean_commit_range_passes_and_bad_range_exits_2(repo: Path) -> None:
    assert main(["--commits", "HEAD~0..HEAD"], DENY, repo) == 0
    assert main(["--commits", "nope..HEAD"], DENY, repo) == 2


def test_f02_oq013_large_file_warns_on_stderr_but_is_still_scanned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("leakscan.cli.LARGE_FILE_BYTES", 5)
    (tmp_path / "big.txt").write_text("FooBarCo and more text\n")
    assert main(["."], DENY, tmp_path) == 1
    assert "over 200 MB" in capsys.readouterr().err
