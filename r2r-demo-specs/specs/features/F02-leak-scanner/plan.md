# F02 · Plan
- Package `tools/leakscan` (uv workspace member) with `src/leakscan/{cli.py,load.py,scan.py,readers.py}`.
- File discovery: `git ls-files -z` plus `git diff --cached --name-only -z`. Binary detection skips non-text files except the supported readers.
- Readers: text (utf-8, errors=replace), xlsx (openpyxl read-only), parquet (pyarrow schema plus first 1000 rows of string columns), Delta (deltalake → arrow, same rule) for paths under `**/fixtures/**`.
- Compile one big case-insensitive regex with `\b` boundaries for plain terms. Keep regex entries separate.
- Exit codes: 0 clean, 1 findings or CI config error, 2 usage error.

## Deviations
