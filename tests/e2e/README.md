# tests/e2e

Playwright specs for the Overview (F10-AC-01 to AC-06, AC-08), including axe and Lighthouse accessibility checks, and
for the batch drawer and windows (F19: `08` need-by window, `09` read-only, `12` drawer, `13` status log, `17` Inbound
and Sample Data windows). F14 adds the full run-of-show.

```bash
make up && make seed     # the stack must be running with the canonical data
make e2e                 # or: make e2e-headed
```

`make e2e` runs against the already-running stack. The live-update spec (F10-AC-05) approves B1042's sample, so run
`make seed` again before the next run. F13/F14 switch `make e2e` to run `make demo-reset` first.
`npm run screenshot` (in this folder) writes `docs/screenshots/overview.png` at 1440×900.

`npm run screenshot:windows` writes the F19 screenshots (`drawer-b4410.png` and the five `win-*.png`) to `docs/screenshots/`.
Run it right after `make seed`: B1042's sample is unapproved only until the live-update spec runs. Most F19 specs add
Status Log entries (insert-only), so a second run shows longer histories until the next demo reset (F13).

## F12: the agents

`20-agents.spec.ts` needs no model (the Agents page, the Insights window and the drawer before any run).
`21-agent-flow.spec.ts` runs the agent from the committed recordings (act 6) and is skipped, with the reason, until
`make record-agents` has written them. Both start by emptying the agent tables through the compose Postgres, which
is what the demo reset will do (F13). `npm run screenshots:agents` writes `agents-inbox.png`, `proposal-b5003.png`,
`trace-b5003.png` and `insights-proposals.png` to `docs/screenshots/`; it runs the agent first, so it needs the
recordings too.
