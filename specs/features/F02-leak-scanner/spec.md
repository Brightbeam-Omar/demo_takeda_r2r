# F02 · Leak Scanner

## Context
The demo must never contain client-identifying terms (constitution P5). The scanner has to know which terms to look for, but **the denylist itself is sensitive** and must never be committed.

## Functional requirements
| ID | Requirement |
|---|---|
| F02-FR-01 | CLI `python -m leakscan [paths…]` scans all git-tracked text files (plus staged files), excluding `.leakscan/` |
| F02-FR-02 | Denylist source, in priority order: env `LEAKSCAN_DENYLIST` (newline-separated), then file `.leakscan/denylist.txt` (gitignored). If neither exists, it prints a **warning** and exits 0 locally, but exits **1 in CI** (`CI=true`) |
| F02-FR-03 | Matching is case-insensitive on word boundaries. Entries may be plain terms or `re:` prefixed regexes. Entries starting with `#` are comments |
| F02-FR-04 | Also scans: `.xlsx` (cell text via openpyxl), `.csv`, `.json`, `.parquet` column names, and **Delta table data under any test fixture folder** |
| F02-FR-05 | Output: `file:line: <masked term> (rule #n)`. The term is masked (first letter + `***`) so CI logs do not leak it either |
| F02-FR-06 | Committed `.leakscan/denylist.example.txt` holds only obviously fake examples (`acme-real-client`, `re:\bsecretsite\b`) and instructions |
| F02-FR-07 | `make check` runs it. CI reads the denylist from a GitHub secret `LEAKSCAN_DENYLIST` |
| F02-FR-08 | Allow-list file `.leakscan/allow.txt` (committed) for false positives, matched as `path:term-hash`. Uses a SHA-256 of the lowercase term so allow entries do not reveal terms |

## Acceptance criteria
- **F02-AC-01** Given denylist `foobarco` and a file containing "FooBarCo plant", then the scan fails and prints `f***`.
- **F02-AC-02** Given the term inside an `.xlsx` cell, then the scan fails with sheet!cell reference.
- **F02-AC-03** Given `CI=true` and no denylist, then exit 1 with a clear message.
- **F02-AC-04** Given an allow-list hash for a path/term, then that occurrence is ignored.
- **F02-AC-05** The repo contains no denylist content (a test asserts `.leakscan/denylist.txt` is gitignored).

## Note for the human
Populate `.leakscan/denylist.txt` locally and the `LEAKSCAN_DENYLIST` GitHub secret with the reference client's company, site, system, campaign, supplier and people names, internal platform names and email domains. Keep this list off any shared drive that prospects can see.
