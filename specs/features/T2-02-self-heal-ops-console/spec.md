# T2-02 · Safety Poll Self-Heal, Ops Console, Alerts

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Show resilience live (act 4) and give a single operations pane.

## Scope
- Safety poll loop in `app-worker` (every 60 s demo): compare `watermark.run_id` vs `pipeline_status_v.last_run_id`; if stale enqueue `sync_event(source='poll')` (never pulls directly)
- Scenario steps `break-webhook` (sets an invalid secret on the pipeline side) and `fix-webhook`
- Ops console page: pipeline runs (from run log), per-source freshness surfaced **in the UI** (with stale-source warning even if pipeline succeeded), queue depth, drain latency, sync failures, agent run counts/errors, runbook links (markdown in `docs/runbooks/`)
- Alert rules evaluated app-side with banner in top bar (stale > threshold, failed sync, HMAC rejects)
- Failed pipeline runs visible (from `pipeline_run_log`) distinguishing 'no run yet' from 'last run failed'

## Acceptance sketch
- With webhook broken, data converges within one poll interval after a pipeline run
- A source whose max(updated_at) stops advancing shows a stale-source warning while pipeline is green
