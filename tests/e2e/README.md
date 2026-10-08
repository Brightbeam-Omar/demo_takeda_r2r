# tests/e2e

Playwright specs for the Overview (F10-AC-01 to AC-06, AC-08), including axe and Lighthouse accessibility checks, and
for the batch drawer and windows (F19: `08` need-by window, `09` read-only, `12` drawer, `13` status log, `17` Inbound
and Sample Data windows), and `specs/00-run-of-show.spec.ts` (F14), the presenter's path through acts 2, 3, 5 and 6.

```bash
make up
make e2e                 # or: make e2e-headed
```

Everything runs against the built frontend on http://localhost:8080 (`FRONTEND_URL` overrides it). There are two
Playwright projects (F14, OQ-162). `run-of-show` is `00-run-of-show.spec.ts`: it needs the untouched demo-start state, in
which it approves B1042, adjusts B2077 and runs the agent, and it must finish in under 6 minutes (the reset is not part of
that). `specs` is every other spec. `make e2e` runs `make demo-reset`, the `run-of-show` project, a second
`make demo-reset`, then the `specs` project, so each starts from the same demo-start state (the live-update spec,
F10-AC-05, approves B1042's sample too, and the Demo Controls spec resets again). Reports: `artifacts/e2e/run-of-show` and
`artifacts/e2e/specs`; a failed run keeps its screenshot and trace in `artifacts/e2e-results/`. Run one project with
`npx playwright test --project=specs` after a reset.

`make record-video` runs the run-of-show alone with `RECORD_VIDEO=1 PACE=presenter`: 4 to 6 s on each key screen, a
visible pointer that glides to each element before a slow click, and a caption bar with the act and one line of what is
happening (no voice-over). It makes one continuous recording of about 7 to 8 minutes at 1440×900 in
`artifacts/video/run-of-show.webm`. `PACE=ci` (the default) is full speed with no overlay, as `make e2e` runs it. `node video-size.mjs <file>` prints a video's
size and length.
`npm run screenshot` (in this folder) writes `docs/screenshots/overview.png` at 1440×900.

`npm run screenshot:windows` writes the F19 screenshots (`drawer-b4410.png` and the five `win-*.png`) to `docs/screenshots/`.
Run it right after `make demo-reset`: B1042's sample is unapproved only until the live-update spec runs. Most F19 specs
add Status Log entries (insert-only), so a second run shows longer histories until the next demo reset.

## F12: the agents

`20-agents.spec.ts` needs no model (the Agents page, the Insights window and the drawer before any run).
`21-agent-flow.spec.ts` runs the agent from the committed recordings (act 6) and is skipped, with the reason, until
`make record-agents` has written them. Both start by emptying the agent tables through the compose Postgres (the demo reset does the same, with the rest). `npm run screenshots:agents` writes `agents-inbox.png`, `proposal-b5003.png`,
`trace-b5003.png` and `insights-proposals.png` to `docs/screenshots/`; it runs the agent first, so it needs the
recordings too.

## F13: Demo Controls

`22-demo-controls.spec.ts` drives the Demo Controls page as Admin: the reset with its live progress, `lims-approve-B1042`
and its refused second run, `ud-post-B5003`, and a final reset. It takes a few minutes (three resets) and leaves the demo
in its starting state. `npm run screenshots:demo` writes `docs/screenshots/demo-controls.png`.
