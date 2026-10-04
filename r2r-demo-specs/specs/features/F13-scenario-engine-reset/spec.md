# F13 · Scenario Engine & Demo Reset

## Context
The presenter needs one-click, repeatable control of the story (constitution P7). Scenario steps go through the **real** source event APIs, so everything downstream happens for real.

## Functional requirements
| ID | Requirement |
|---|---|
| F13-FR-01 | Steps are declared in `services/sources/scenario/scenarios/site_a.yaml`: `id`, `title`, `talk_track` (one line for the presenter), `actions` (ordered: `event` to a source API, `clock_advance`, `run_pipeline`, `wait_sync`, `run_agent`), and `preconditions` (simple state checks, e.g. "B1042 stage == qc_testing") |
| F13-FR-02 | Tier 1 steps: `lims-approve-B1042` (LIMS approve + run pipeline + wait sync) · `ud-post-B5003` (ERP UD accept + pipeline + sync; resolves air gap) · `open-deviation-B1042` · `close-deviation-B3150` · `advance-day` (clock +1 day + pipeline + sync) · `run-pipeline` · `airgap-agent` (run agent for candidates) · `pull-forward-B2077` (fallback: performs the act 5 edit through the API as Pat, if the live click fails) |
| F13-FR-03 | API: `GET /scenario/steps` (with precondition status), `POST /scenario/steps/{id}/run` → streams progress (Server-Sent Events) per action, `POST /scenario/reset` |
| F13-FR-04 | `make scenario STEP=<id>` calls the API and prints progress. Exit non-zero on failure |
| F13-FR-05 | **Reset** (`make demo-reset` and `POST /scenario/reset`): stop the agents autorun → truncate app tables except `app_user` and `alembic_version` (and reset `demo_clock` to `demo.start_datetime`) → launch Dagster job `r2r_reset_lakehouse` → `datagen generate` with the profile seed → run pipeline → wait for sync `done` → health summary. Target < 3 min. Idempotent |
| F13-FR-06 | **Demo Controls** panel on `/admin` (admin persona, DEMO_MODE): list of steps with title, talk track, precondition indicator, Run button, live progress log, and a "Reset demo" button with confirm |
| F13-FR-07 | Step runs are recorded in `audit_event(action='scenario_step')` with the step id and outcome |
| F13-FR-08 | Wait semantics: `wait_sync` polls `/api/sync/status` until the watermark equals the run_id of the pipeline run started in the same step (timeout 120 s) |

## Acceptance criteria
- **F13-AC-01** `make demo-reset` completes in < 3 min and leaves: clock at start, 5 story batches in their setup states, published + mirrored data, and no proposals.
- **F13-AC-02** Running `lims-approve-B1042` moves B1042 to `qa_release` in the API within 90 s. Running it again fails its precondition with a clear message (no double approval).
- **F13-AC-03** `ud-post-B5003` removes B5003 from air-gap alerts after sync.
- **F13-AC-04** The Demo Controls panel shows live progress lines for each action.
- **F13-AC-05** `reset` → `lims-approve-B1042` → `reset` returns the system to an identical state (compare published `batch_pipeline_v` checksums).
