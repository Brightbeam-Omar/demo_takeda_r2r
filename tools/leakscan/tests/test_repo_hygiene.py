"""Repo-level guarantees [F02-AC-05, F02-FR-06]: no denylist content in the repo."""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)


@pytest.mark.skipif(not (REPO_ROOT / ".git").exists(), reason="needs a git checkout")
def test_f02_ac05_denylist_file_is_gitignored_and_not_tracked() -> None:
    """F02-AC-05: .leakscan/denylist.txt is gitignored, so no denylist content can be committed."""
    assert _git("check-ignore", "-q", ".leakscan/denylist.txt").returncode == 0
    assert _git("ls-files", ".leakscan/denylist.txt").stdout.strip() == ""


def test_f02_fr06_example_denylist_has_only_fake_entries() -> None:
    lines = (REPO_ROOT / ".leakscan" / "denylist.example.txt").read_text().splitlines()
    entries = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    assert entries == ["acme-real-client", r"re:\bsecretsite\b"]
