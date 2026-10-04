# F04 · Plan
- One FastAPI app per source: `services/sources/{erp_sim,lims_sim,qms_sim}/src/<name>/{app.py, models.py, events.py, db.py}` with `migrations/`.
- Shared helper in `r2r_core.db`: SQLAlchemy engine factory per DSN, `stamp(model)` sets `updated_at = clock.now()`.
- The event endpoints are thin. Domain consistency lives in `events.py` functions, which are also importable by the generator (F05), so seeded and live data are created the same way.
- `scenario` service: `services/sources/scenario/src/scenario/{app.py, clock_api.py}` (steps arrive in F13).

## Deviations
