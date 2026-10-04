# services/datagen

Seeded synthetic data generator (F05). It builds a complete, generic site history and replays it through the
F04 event functions, so seeded data and live scenario data are written the same way.

```bash
uv run python -m datagen generate --profile site_a --seed 4242     # wipe and populate the three source DBs
uv run python -m datagen legacy-workbook --out artifacts/legacy_tracker.xlsx
```

Outputs land in `artifacts/`: `datagen_report.md`, `expected_stages.csv` (an oracle for F06, never loaded
into a source DB) and the legacy workbook. Every tuning number lives in `src/datagen/params.yaml`.
