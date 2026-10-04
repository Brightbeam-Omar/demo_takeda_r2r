# F04 · Source Simulators & Clock Service

## Context
These are realistic stand-ins for ERP, LIMS and QMS, each with its own database and a small API. The pipeline reads their databases. Agents and the scenario engine use their APIs. The `scenario` service owns the demo clock.

## Functional requirements
| ID | Requirement |
|---|---|
| F04-FR-01 | Alembic-managed schemas for `erp_sim`, `lims_sim` and `qms_sim` exactly as in `04-data-contracts` §1, including keys, FKs where natural, indexes on `updated_at` and on `(matnr, charg)` / `(material_no, batch_no)` |
| F04-FR-02 | Every table has `updated_at timestamptz not null`, set from the **demo clock** by the service on every write (a DB trigger is not acceptable, because the demo clock is not DB time) |
| F04-FR-03 | `erp-sim` API (port 8101): `GET /health`, `GET /materials`, `GET /batches/{matnr}/{charg}`, `GET /lots/{prueflos}`, plus **write endpoints used only by the scenario engine**: `POST /events/goods-receipt`, `/events/transfer`, `/events/inbound-check`, `/events/usage-decision`, `/events/hold`, `/events/demand`. Each validates input and writes consistent rows (e.g. GR creates `mseg` 101, `mchb` stock, `qals` lot 01 and `zinbchk` open) |
| F04-FR-04 | `lims-sim` API (8102): `GET /samples?batch_no=&material_no=`, `GET /samples/{id}`, `GET /samples/{id}/results`. Scenario writes: `POST /events/sample-collected`, `/events/sample-shipped`, `/events/testing-started`, `/events/approved`, `/events/rejected` |
| F04-FR-05 | `qms-sim` API (8103): `GET /deviations?batch_no=`, `GET /deviations/{no}`. Scenario writes: `POST /events/deviation-opened`, `/events/deviation-closed` |
| F04-FR-06 | Write endpoints require header `X-Scenario-Token` (env `SCENARIO_TOKEN`). Read endpoints are open on the compose network |
| F04-FR-07 | `scenario` service (8100) with clock endpoints: `GET /clock` → `{now_utc, today_local, frozen}`, `POST /clock/set {iso}`, `POST /clock/advance {hours|days}`. It persists to `app.demo_clock`. **F04 owns this table**: it creates the app DB's first Alembic migration (in the `app_api` package skeleton, `0001_demo_clock`), which F08 extends. The clock moves only via set/advance (no wall-time ticking) |
| F04-FR-08 | OpenAPI docs enabled on every service at `/docs` (a demo talking point) |
| F04-FR-09 | All services in docker-compose with health checks. `make up` brings them up after postgres is healthy and runs migrations on start |

## Acceptance criteria
- **F04-AC-01** After `make up`, `GET :8101/health`, `:8102/health`, `:8103/health` and `:8100/clock` return 200.
- **F04-AC-02** `POST /events/goods-receipt` for a new batch creates consistent rows in `mseg`, `mchb`, `mcha`, `qals` (art 01) and `zinbchk` (open), all with `updated_at` = demo now.
- **F04-AC-03** Writes without the scenario token return 401.
- **F04-AC-04** `POST /clock/advance {"days":1}` moves `GET /clock` forward exactly 24 h, and `r2r_core.clock.now()` in another container reflects it within 2 s.
- **F04-AC-05** `POST /events/usage-decision` with a code not in the profile's UD codes returns 422.
- **F04-AC-06** LIMS `approved` sets `sample.status='approved'` and `approved_at` = demo now.

## Out of scope
Spreadsheet/3PL sources (T2-01, T2-07) and an S/4-like view set (T2-07).

## Notes from other features
- **Clock contract needed by F03 (`HttpClock`, OQ-018):** `GET /clock` must return JSON that includes `now_utc` (ISO 8601, timezone-aware) and `frozen` (bool), for example `{"now_utc": "2026-10-12T07:00:00+00:00", "frozen": false}`. Extra fields such as `today_local` (F04-FR-07) are fine. `r2r_core.clock.HttpClock` reads only `now_utc`.

