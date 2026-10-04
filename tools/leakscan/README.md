# leakscan

Client-term leak scanner (constitution P5). `make check` runs it.

```bash
uv run python -m leakscan                          # git-tracked, staged and untracked-but-not-ignored files
uv run python -m leakscan artifacts/ some/file.xlsx  # exactly these paths, recursively, regardless of git
uv run python -m leakscan --commits 'origin/main..HEAD'   # commit messages and author names
```

Exit codes: `0` clean, `1` findings (or no denylist when `CI=true`), `2` usage or configuration error.
Output is `file:line: F*** (rule #n)`: the matched text is masked, so logs never carry the term.

## Denylist (never committed)

1. Env `LEAKSCAN_DENYLIST`: the list itself, newline-separated (not a path). Used in CI as a GitHub secret.
2. Else `.leakscan/denylist.txt` (gitignored). Copy `.leakscan/denylist.example.txt` and fill it in.

Plain terms match case-insensitively with no letter or digit on either side (so `-`, `.`, `@` work inside a
term). `re:` entries are regular expressions used as written. With no denylist the scan warns and passes
locally, and fails in CI.

## What is scanned

Text files (csv, json and so on), `.xlsx` cells (`Sheet!B3`), text inside `.docx` and `.pptx`, parquet column
names and every string value, Delta tables (their parquet files and JSON log), and the file paths
themselves. Other binaries (`.pdf`, images) are skipped and listed in the summary. `.leakscan/` is never
scanned.

## False positives

Add `<repo-relative path>:<sha256 of the lowercased matched text>` to `.leakscan/allow.txt`, for example:

```bash
printf %s 'the matched text' | tr 'A-Z' 'a-z' | shasum -a 256
```
