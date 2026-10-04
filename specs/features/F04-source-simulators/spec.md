# F04 · Source Simulators & Clock Service

## Context
These are realistic stand-ins for ERP, LIMS and QMS, each with its own database and a small API. The pipeline reads their databases. Agents and the scenario engine use their APIs. The `scenario` service owns the demo clock.

## Functional requirements
| ID | Requirement |
|---|---|
| F04-FR-01 | Alembic-managed schemas for `erp_sim`, `lims_sim` and `qms_sim` exactly as in `04-data-contracts` §1, including keys, FKs where natural, indexes on `updated_at` and on `(matnr, charg)` / `(material_no, batch_no)` |
| F04-FR-02 | Every table has `updated_at timestamptz not null`, set from the **demo clock** by the service on every write (a DB trigger is not acceptable, because the demo clock is not DB time) |
| F04-FR-03 | `erp-sim` API (port 8101): `GET /health`, `GET /materials`, `GET /batches/{matnr}/{charg}` (the batch with its stock rows, movements and lots), `GET /lots/{prueflos}`, plus **write endpoints used only by the scenario engine**, each validating input and writing consistent rows in one transaction: `POST /events/goods-receipt` (creates `mcha`, `mseg` 101, `mchb` stock in QI, `qals` lot 01 and an `open` `zinbchk`), `/events/goods-receipt-reversal` (posts `mseg` 102 and takes the quantity out of QI; batch, lot and check rows stay), `/events/transfer` (`311`), `/events/inbound-check`, `/events/usage-decision`, `/events/reeval-lot` (opens a `09` lot on an existing batch; creates a `zinbchk` row only when `inbound_check` is `open`, `passed` or `failed`, default `none`), `/events/stock-block` and `/events/stock-unblock` (move quantity between QI and blocked), `/events/hold` (`{matnr, charg, hold}` sets `mcha.zstat` to `H` or empty) and `/events/demand` (`{id?, matnr, campaign, requirement_date, quantity, is_open}` upserts by `id`; closing a demand is `is_open=false`). Stock movement rules are in `04-data-contracts` §1.1 |
| F04-FR-04 | `lims-sim` API (8102): `GET /samples?batch_no=&material_no=`, `GET /samples/{id}`, `GET /samples/{id}/results`. Scenario writes: `POST /events/sample-collected` (new sample `registered`; a lot may get a new sample only if its latest sample is `rejected`), `/events/sample-shipped` (offsite samples only), `/events/testing-started`, `/events/approved` (`approved_at` = demo now), `/events/rejected`. Sample ids are `S-0000001`-style |
| F04-FR-05 | `qms-sim` API (8103): `GET /deviations?batch_no=`, `GET /deviations/{no}` (with its batch links). Scenario writes: `POST /events/deviation-opened` (takes `links: [{material_no, batch_no}]`), `/events/deviation-closed` |
| F04-FR-06 | Write endpoints (every `POST`, including `POST /clock/set` and `POST /clock/advance`) require header `X-Scenario-Token` (env `SCENARIO_TOKEN`). A missing or wrong token returns 401 (constant-time compare; an unset server token rejects everything). Read endpoints are open on the compose network |
| F04-FR-07 | `scenario` service (8100) with clock endpoints: `GET /clock` → `{now_utc, today_local, frozen}` (`today_local` in the profile's timezone, `frozen` always false for now), `POST /clock/set {"iso": "<timezone-aware ISO 8601>"}` (naive input is 422) and `POST /clock/advance` with exactly one of `{"hours": n}` or `{"days": n}`, `n` a positive integer (zero, negative or both is 422; going back is done with `set`). The advance is one atomic SQL update of `app.demo_clock`. The service inserts the `id=1` row on first start from the profile's `demo.start_datetime` and never overwrites an existing row. It reads and writes the clock with `CLOCK_SOURCE=db`. **F04 owns this table**: it creates the first Alembic migration of the app DB (in the `app_api` package skeleton, `0001_demo_clock`, nothing else), which F08 extends. The clock moves only via set/advance (no wall-time ticking) |
| F04-FR-08 | OpenAPI docs enabled on every service at `/docs` (a demo talking point) |
| F04-FR-09 | All services in docker-compose with health checks. `make up` brings them up after postgres is healthy and runs migrations on start: a one-shot `db-migrate` service migrates the `app` DB and the others wait for it (`service_completed_successfully`); each simulator runs Alembic for its own DB in its entrypoint before starting |
| F04-FR-10 | **Event conventions.** (1) Event bodies carry explicit business dates (`budat`, `pastrterm`, `collected_date`, `vdatum`, ...) that default to the demo's today when omitted. (2) `updated_at` is stamped with `r2r_core.clock.now()`: over HTTP that is the demo clock; the generator (F05) calls the same functions in-process with a `FixedClock` set to each simulated day. Event functions take no clock argument. (3) Document, lot, sample and deviation numbers come from a counter table per DB; a body may pass an explicit number, and allocation skips numbers already in use. (4) A duplicate create (same natural key) returns 409 and writes nothing; invalid input (unknown reference, code not in the profile, impossible state change) returns 422. (5) Responses return the created or changed rows as JSON. (6) Read endpoints return table rows as JSON with the column names of `04-data-contracts` §1 |
| F04-FR-11 | **Test layers.** Unit tests run in `make check` (validation, token guard, helpers). DB-backed tests are marked `integration` and run against real Postgres with `make integration` and in the CI `integration` job. Acceptance tests marked `stack` run against `make up` containers with `make stack-test`; the CI `stack` job runs them on pull requests only |

## Acceptance criteria
- **F04-AC-01** After `make up`, `GET :8101/health`, `:8102/health`, `:8103/health` and `:8100/clock` return 200.
- **F04-AC-02** `POST /events/goods-receipt` for a new batch creates consistent rows in `mseg`, `mchb`, `mcha`, `qals` (art 01) and `zinbchk` (open), all with `updated_at` = demo now.
- **F04-AC-03** Writes without the scenario token (or with a wrong one) return 401, on every simulator and on the clock `POST`s.
- **F04-AC-04** `POST /clock/advance {"days":1}` moves `GET /clock` forward exactly 24 h, and `r2r_core.clock.now()` in another container (`CLOCK_SOURCE=http`) reflects it within 2 s.
- **F04-AC-05** `POST /events/usage-decision` with a code not in the profile's UD codes returns 422.
- **F04-AC-06** LIMS `approved` sets `sample.status='approved'` and `approved_at` = demo now.

## Out of scope
Spreadsheet/3PL sources (T2-01, T2-07) and an S/4-like view set (T2-07).

## Notes from other features
- **Clock contract needed by F03 (`HttpClock`, OQ-018):** `GET /clock` must return JSON that includes `now_utc` (ISO 8601, timezone-aware) and `frozen` (bool), for example `{"now_utc": "2026-10-12T07:00:00+00:00", "frozen": false}`. Extra fields such as `today_local` (F04-FR-07) are fine. `r2r_core.clock.HttpClock` reads only `now_utc`.

