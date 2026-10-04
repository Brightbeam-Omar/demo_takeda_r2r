# F04 · Plan
- One FastAPI app per source: `services/sources/{erp_sim,lims_sim,qms_sim}/src/<name>/{app.py, models.py, events.py, db.py}` with `migrations/`.
- Shared helper in `r2r_core.db`: SQLAlchemy engine factory per DSN, `stamp(model)` sets `updated_at = clock.now()`.
- The event endpoints are thin. Domain consistency lives in `events.py` functions, which are also importable by the generator (F05), so seeded and live data are created the same way.
- `scenario` service: `services/sources/scenario/src/scenario/{app.py, clock_api.py}` (steps arrive in F13).

## Deviations
- **Decisions OQ-024 to OQ-030** are recorded in `specs/OPEN_QUESTIONS.md` and implemented as decided; the contract changes are in `04-data-contracts` §1 and this feature's `spec.md`.
- **`reeval-lot` and the inbound check (refines OQ-028):** the event creates a `zinbchk` row only when its `inbound_check` field is `open`, `passed` or `failed`; the default is `none` (no row). A re-evaluation lot with an `open` check would sit at the receipt stage, which the re-evaluation SLA table does not cover.
- **Layout:** migrations live inside each package (`<pkg>/migrations`) and are run by `python -m <pkg>.migrate` (an Alembic runner in `r2r_core.db`), so they ship in the image. Initial revisions were generated with `alembic revision --autogenerate` against an empty scratch database.
- **Shared code in `r2r_core`:** `db` (DSNs, stamping session factory, counters, `row_dict`, Alembic runner), `web` (token guard, error mapping, health, event-route registration) and `errors` (`Conflict` is 409, `Invalid` is 422). `r2r_core` now depends on `sqlalchemy`, `alembic` and `fastapi`.
- **`updated_at`** is stamped by a session `before_flush` hook (new or really modified rows), one timestamp per session, from `r2r_core.clock.now()`. Event functions take no clock argument.
- **Quantities in JSON** are strings (`"100.000"`), the default Pydantic encoding of `Decimal`: no precision is lost.
- **Business rules added where the spec was silent:** a lot gets a new sample only when its latest sample is rejected; offsite samples must be shipped before testing or approval; a lot gets one usage decision; a `reeval-lot` is refused while another is open; a `311` keeps stock in the same buckets and deletes an emptied source row; a reversal only takes quantity out of QI.
- **Tests:** `conftest.py` at the repo root creates throwaway databases for `integration` tests; `tests/stack` holds the acceptance tests run by `make stack-test`. pytest's default selection excludes both markers. The CI `integration` job now runs every `integration` test, and a new `stack` job runs on pull requests only.
- **Stack tests insert minimal ERP master data** directly in Postgres (the ERP has no master-data endpoint; F05 seeds it) and restore the demo clock afterwards.
- **Not done here:** the simulators do not seed any data (F05); scenario steps and demo reset (F13).

