# F14 · Plan
- Playwright config with `baseURL=http://localhost:8080` (nginx build, OQ-159) and a 1440×900 viewport. The run-of-show is `specs/00-run-of-show.spec.ts` (OQ-162); a `run-of-show` project runs only it. Helpers: `asPersona(page, key)`, `runStep(page, id)`, `openRow(page, key)`.
- The demo script is written for the domain SME and the presenter: plain language and no jargon in the talk tracks.
- `make doctor` is a Python package `tools/doctor` (`mypy --strict`, unit tests with an injected command runner), run through `uv run python -m doctor`. One function per check returning `ok | fail | skipped`, a message and a fix. It reads ports and health URLs from `.env` and `docker-compose.yml` defaults. The replay check calls `GET /agents/air_gap/replay-check` (a small read-only F12 addition, OQ-160) through the agents host port.
- `make demo-reset` runs a shell guard first: `docker compose exec -T agents sh -c 'ls /recordings/air_gap | wc -l'`; zero or an error means `docker compose up -d --force-recreate --wait agents` (OQ-153).
- Demo Controls: `disabled={running || step.preconditions === "unmet"}` with `title` set to the reason; the disabled button needs the tooltip on a wrapper `span`, since browsers do not fire hover on disabled buttons (OQ-154).
- `formatSiteDateTime` in `frontend/src/lib/format.ts` with unit tests; the summary text goes through a `withSiteTimes(text, tz)` replace on ISO tokens (OQ-155).
- Video: `PACE=presenter` adds `beat()` pauses; `make record-video` resets, runs the `run-of-show` project with `video: {mode: 'on', size: {width: 1440, height: 900}}`, copies the file to `artifacts/video/` (OQ-164).
- `docs/demo-script.md` is checked by `tools/checks` (leak scan of the file, step ids exist, the five headings per act).

## Deviations
