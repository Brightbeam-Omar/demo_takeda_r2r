# F14 · Run-of-Show E2E, README, Rehearsal Kit

## Functional requirements
| ID | Requirement |
|---|---|
| F14-FR-01 | Playwright test `tests/e2e/run_of_show.spec.ts` that executes acts 2, 3, 5 and 6 of `01-product-overview` §6 exactly as a presenter would (persona switches, clicks, scenario steps through the Demo Controls UI), with assertions at each beat. Runs with `LLM_PROVIDER=replay`. The acts use the parity UI (F15–F21): act 5 is W6 Adjust Needs-by on B2077; act 6 runs the agent from the Insights window and the Agents page; "Explain this number" uses the ⓘ popovers |
| F14-FR-02 | `make e2e` = `make demo-reset` then Playwright headless, with an HTML report in `artifacts/e2e/`. `make e2e-headed` for watching it |
| F14-FR-03 | `docs/demo-script.md`: presenter script per act with exact clicks, talk track, the "why it matters" line, timings, and recovery moves (e.g. use the `pull-forward-B2077` fallback step) |
| F14-FR-04 | `docs/architecture-overview.md`: a one-page generic architecture diagram (Mermaid) and a "how this maps to a customer stack" table (lakehouse → Databricks, ERP sim → SAP ECC/S4, LIMS/QMS sims → customer systems, auth → SSO) |
| F14-FR-05 | `make doctor`: checks Docker running, ≥ 12 GB allocated to Docker, ports free, `.env` present, denylist present, replay recordings present. Prints fixes |
| F14-FR-06 | README completed: quickstart (≤ 6 commands), presenter checklist (night before / 30 min before), troubleshooting (top 10 issues), offline mode note |
| F14-FR-07 | `make record-video`: runs the Playwright run-of-show with video recording to `artifacts/video/` as a backup asset |

## Acceptance criteria
- **F14-AC-01** On a clean clone on an Apple Silicon Mac with 16 GB available to Docker with Wi-Fi off (after images are pulled), `make doctor && make e2e` passes.
- **F14-AC-02** The run-of-show test completes in < 6 min.
- **F14-AC-03** Someone new follows the README and runs the demo in < 15 min (manual check by a second person, noted in the PR).
- **F14-AC-04** The leak scan is clean on the entire repo, including `artifacts/`.
