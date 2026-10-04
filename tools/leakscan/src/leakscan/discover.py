"""Decide which files to scan [F02-FR-01].

No path arguments: git-tracked, staged and untracked-but-not-ignored files, minus ``.leakscan/``.
With path arguments: exactly those files or directories (recursive), regardless of git.
"""

import subprocess
from pathlib import Path

from leakscan.load import UsageError

EXCLUDED_DIR = ".leakscan"


def git_root(cwd: Path) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True, check=False
    )
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def _git_list(root: Path, *args: str) -> list[str]:
    result = subprocess.run(["git", *args, "-z"], cwd=root, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise UsageError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return [name for name in result.stdout.split("\0") if name]


def display_path(path: Path, root: Path) -> str:
    """Repo-relative posix path; absolute posix path for files outside the root."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _excluded(display: str) -> bool:
    return display == EXCLUDED_DIR or display.startswith(EXCLUDED_DIR + "/")


def default_files(root: Path) -> list[Path]:
    names = {
        *_git_list(root, "ls-files"),
        *_git_list(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR"),
        *_git_list(root, "ls-files", "--others", "--exclude-standard"),
    }
    files = [root / name for name in sorted(names) if not _excluded(name)]
    return [f for f in files if f.is_file() and not f.is_symlink()]


def explicit_files(paths: list[str], cwd: Path, root: Path) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        target = (cwd / raw).resolve() if not Path(raw).is_absolute() else Path(raw)
        if target.is_dir():
            for child in sorted(target.rglob("*")):
                if ".git" in child.relative_to(target).parts:
                    continue
                if child.is_file() and not child.is_symlink():
                    found.append(child)
        elif target.is_file():
            found.append(target)
        else:
            raise UsageError(f"path does not exist: {raw}")
    return [f for f in found if not _excluded(display_path(f, root))]
