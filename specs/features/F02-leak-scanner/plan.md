# F02 · Plan
- Package `tools/leakscan` (uv workspace member) with `src/leakscan/{cli.py,load.py,scan.py,readers.py}`.
- File discovery: `git ls-files -z` plus `git diff --cached --name-only -z`. Binary detection skips non-text files except the supported readers.
- Readers: text (utf-8, errors=replace), xlsx (openpyxl read-only), parquet (pyarrow schema plus first 1000 rows of string columns), Delta (deltalake → arrow, same rule) for paths under `**/fixtures/**`.
- Compile one big case-insensitive regex with `\b` boundaries for plain terms. Keep regex entries separate.
- Exit codes: 0 clean, 1 findings or CI config error, 2 usage error.

## Deviations
- **No separate Delta reader (T3):** Delta tables are parquet data files plus a JSON log, and the scanner reads both as ordinary files (every string value, all rows, per OQ-013). A dedicated `deltalake` reader would scan the same data twice. `deltalake` is therefore only used by the tests to build a real Delta table. It is still declared as a `tools/leakscan` dependency, as approved in OQ-016.
- **Extra modules:** `allow.py`, `discover.py`, `commits.py` and `__main__.py` alongside the planned `cli.py`, `load.py`, `scan.py`, `readers.py`.
- **Masking keeps case (OQ-012):** F02-AC-01 shows `f***` for the input `FooBarCo`. Per the OQ-012 decision the mask is the first character *of the matched text*, so the output is `F***`. The AC test asserts `F***`.
- **Boundary rule consequence (OQ-012):** a plain entry that starts with a non-alphanumeric character (for example `@client.example`) cannot match straight after a letter. Write such entries without the leading symbol (`client.example`).
- **Commit scanning (OQ-014):** author name and email are scanned as location `author`, message lines by line number. Findings use the virtual path `commits/<full sha>`, which is also the allow-list path. `--commits` scans commits only, not files.
- **`CI` truthiness:** `true` or `1`, case-insensitive. An env value or file that holds no rules counts as no denylist.
- **Locations that match a rule are masked:** a sheet or column named after a term prints as `[location masked]`.
- **Xlsx via openpyxl read-only mode:** reads formulas as text, not cached results; cell comments are not read.
- **Office files:** every XML part inside `.docx` and `.pptx` is read with the standard-library XML parser. Embedded images and other binaries inside the archive are not scanned.

