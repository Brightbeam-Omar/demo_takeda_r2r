# F14 · Run-of-Show E2E, README, Rehearsal Kit

## Functional requirements
| ID | Requirement |
|---|---|
| F14-FR-01 | Playwright test `tests/e2e/specs/00-run-of-show.spec.ts` (OQ-162) that executes acts 2, 3, 5 and 6 of `01-product-overview` §6 exactly as a presenter would (persona switches, clicks, scenario steps through the Demo Controls UI), with assertions at each beat. Runs with `LLM_PROVIDER=replay`. The acts use the parity UI (F15–F21): act 5 is W6 Adjust Needs-by on B2077; act 6 runs the agent from the Insights window and the Agents page; "Explain this number" uses the ⓘ popovers |
| F14-FR-02 | `make e2e` = `make demo-reset` then Playwright headless, with an HTML report in `artifacts/e2e/`. `make e2e-headed` for watching it |
| F14-FR-03 | `docs/demo-script.md` (OQ-156, OQ-158, OQ-163): written for the Presenter and the SME in plain language. Per act: exact clicks, talk track, a "why it matters to the customer" line, timings and recovery moves (which Demo Controls step to use if a live click fails, e.g. `pull-forward-B2077`). Covers the 40-minute working-call version and the 12-minute leadership cut. Names no real company or system except the profile terms the UI shows |
| F14-FR-04 | `docs/architecture-overview.md`: a one-page generic architecture diagram (Mermaid) and a "how this maps to a customer stack" table (lakehouse → Databricks, ERP sim → SAP ECC/S4, LIMS/QMS sims → customer systems, auth → SSO) |
| F14-FR-05 | `make doctor` (OQ-152, OQ-160, OQ-161): checks Docker running, Docker memory ≥ 12 GB, ports free (or held by this project), `.env` present, denylist present, the `agents` container's `/recordings` mount non-empty, replay keys present for the 4 demo-start air gaps, and the Dagster and app health endpoints. Every failing check prints its fix (e.g. `docker compose up -d --force-recreate agents`). Non-zero exit when any check fails |
| F14-FR-06 | README completed: quickstart (≤ 6 commands), presenter checklist (night before / 30 min before), troubleshooting (top 10 issues), offline mode note |
| F14-FR-07 | `make record-video` (OQ-157, OQ-164, OQ-165): demo reset, then the Playwright run-of-show with `PACE=presenter` (6 to 8 minutes, dwell, visible pointer, captions, no voice-over), recorded at 1440×900 to `artifacts/video/` as a backup asset. `PACE=ci` is the default for `make e2e` |
| F14-FR-08 | `make demo-reset` recreates the `agents` container (`docker compose up -d --force-recreate agents`) when its `/recordings/air_gap` mount is empty, before resetting (OQ-153) |
| F14-FR-09 | Demo Controls: a step's Run button is disabled when its preconditions are `unmet`, with the reason as the tooltip; `unknown` stays enabled (OQ-154) |
| F14-FR-10 | Presentation: ISO date-times in the proposal evidence table and in the agent summary text display as `11 Oct 2026 02:00` in site time. Stored values are unchanged (OQ-155) |
| F14-FR-11 | `lims-approve-B1042` also records the LIMS results in the ERP (`results-recorded`), stamped 2 demo-hours after the approval, so B1042 never becomes an air gap (OQ-166) |
| F14-FR-12 | In replay mode "Run air-gap agent" processes each candidate independently; a candidate with no recording gets the row message "No recording for B1042: record it or run live" and the others still produce proposals (OQ-167) |
| F14-FR-13 | Demo Controls groups steps by act in script order (Act 3, Act 5, Act 6, After act 6, Extras). `ud-post-B5003` and `interface-sync-B5003` sit under After act 6 and need no proposal pending approval for B5003 (OQ-168) |
| F14-FR-14 | `pull-forward-B2077` is disabled with "B2077 is already adjusted" when an override exists, and writes nothing (OQ-169) |
| F14-FR-15 | Profile `demo.default_columns` is the default Overview column set in `DEMO_MODE`; profile `demo.presets` are re-created by `seed_after_reset()` for every persona (OQ-170) |
| F14-FR-16 | Profile `demo.hide_placeholders: true` hides the Tier 2 placeholder menu items in `DEMO_MODE` (OQ-171) |
| F14-FR-17 | The proposal page and the Agents card show the provider chip, "Replay · recorded from <model>" or "Live · <model>" (OQ-172) |
| F14-FR-18 | CLAUDE.md rule: changes to datagen, the published contract or the agent tools are followed by `make demo-reset && make record-agents && make doctor EXPECT_UP=1` in the same PR; a stack test fails when the replay keys of the 4 demo-start air gaps are missing after a reset (OQ-173) |

## Acceptance criteria
- **F14-AC-01** On a clean clone on an Apple Silicon Mac with 16 GB available to Docker with Wi-Fi off (after images are pulled), `make doctor && make e2e` passes.
- **F14-AC-02** The run-of-show test completes in < 6 min.
- **F14-AC-03** Someone new follows the README and runs the demo in < 15 min (manual check by a second person, noted in the PR).
- **F14-AC-04** The leak scan is clean on the entire repo, including `artifacts/`.
- **F14-AC-05** `make doctor` on the demo-start stack passes. With the `agents` container's recordings mount emptied (or the `agents` container stopped, or `.env` missing) it fails that check, prints its fix, and exits non-zero. After the printed fix, it passes (FR-05).
- **F14-AC-06** With the recordings mount emptied, `make demo-reset` recreates the `agents` container and the air-gap agent then replays all four air gaps (FR-08).
- **F14-AC-07** On Demo Controls, after `lims-approve-B1042` has run, its Run button is disabled and its tooltip says why; a step with `unknown` preconditions stays enabled (FR-09).
- **F14-AC-08** The proposal evidence table and the summary of a replayed B5003 proposal show no `T…Z` ISO text; they show times such as `11 Oct 2026 02:00`; the stored proposal JSON is byte-identical to before (FR-10).
- **F14-AC-09** `docs/demo-script.md` has, for each act, the five headings Clicks, Say, Why it matters, Time, If it goes wrong, plus both versions; the leak scan is clean on it, and every scenario step id it names exists in `site_a.yaml` (FR-03).
- **F14-AC-10** `make record-video` leaves a video of 1440×900 in `artifacts/video/` (FR-07).
- **F14-AC-11** Stack test: reset, `lims-approve-B1042`, `advance-day` twice: the air-gap candidates are still exactly the 4 recorded batches (FR-11).
- **F14-AC-12** With one recording removed, the run creates proposals for the other candidates, the missing one reports "No recording for B1042: record it or run live", and the API answers 200 (FR-12).
- **F14-AC-13** `GET /scenario/steps` returns the groups in script order; the UI shows them as headed sections; `ud-post-B5003` is refused while a B5003 proposal is pending approval (FR-13).
- **F14-AC-14** With an existing B2077 override, `pull-forward-B2077` is `unmet` with "already adjusted", a forced run is refused, and nothing is written (FR-14).
- **F14-AC-15** In `DEMO_MODE` the Overview shows exactly the profile's default columns on a fresh browser; after a reset each persona has the profile's presets (FR-15).
- **F14-AC-16** The four placeholder items are absent from the menu in `DEMO_MODE` with the flag on, and present with it off (FR-16).
- **F14-AC-17** The B5003 proposal page and the Agents card show the provider chip (FR-17).
- **F14-AC-18** After a reset the replay check reports 4 of 4; CLAUDE.md has the rule (FR-18).
