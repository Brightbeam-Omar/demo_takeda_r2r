# tests/e2e

Playwright specs for the Overview (F10-AC-01 to AC-06, AC-08), including axe and Lighthouse accessibility checks.
F14 adds the full run-of-show.

```bash
make up && make seed     # the stack must be running with the canonical data
make e2e                 # or: make e2e-headed
```

`make e2e` runs against the already-running stack. The live-update spec (F10-AC-05) approves B1042's sample, so run
`make seed` again before the next run. F13/F14 switch `make e2e` to run `make demo-reset` first.
`npm run screenshot` (in this folder) writes `artifacts/screenshots/overview.png` at 1440×900.
