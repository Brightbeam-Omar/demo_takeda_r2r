"""F12 / OQ-146: the Anthropic key from ``.env`` appears nowhere a commit or a recording could carry it.

The test reads the key from the environment or the git-ignored ``.env`` and looks for it in every tracked and
unignored file and in every commit message. It never prints the key. Without a key it is skipped.
"""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _key() -> str:
    value = os.environ.get("ANTHROPIC_API_KEY", "")
    env_file = ROOT / ".env"
    if not value and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                value = line.split("=", 1)[1].strip().strip("\"'")
    return value


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def test_f12_oq146_the_api_key_is_in_no_file_and_no_commit_message() -> None:
    key = _key()
    if len(key) < 12:
        pytest.skip("no ANTHROPIC_API_KEY configured")
    needle = key.encode()
    files = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    leaks = [
        name.decode()
        for name in files
        if name and (ROOT / name.decode()).is_file() and needle in (ROOT / name.decode()).read_bytes()
    ]
    assert leaks == [], f"the API key is in {leaks}"
    assert needle not in _git("log", "--all", "--format=%B%n%an%n%ae"), "the API key is in a commit message"
