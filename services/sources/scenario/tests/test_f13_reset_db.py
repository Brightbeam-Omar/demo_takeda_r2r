"""T4: what the demo reset does to the app database [F13-FR-05, F13-AC-01]. Needs Postgres (integration)."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from app_api.db import migrate
from r2r_core.db import make_engine
from r2r_core.profile import load_profile
from scenario.clock_api import seed_clock
from scenario.reset import KEPT, MIRROR_PREFIX, TRUNCATED, clear_app_tables, seed_after_reset
from scenario.runner import write_audit
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration
OPENING = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def engine(make_test_database: Callable[[str], str]) -> Iterator[Engine]:
    dsn = make_test_database("app_reset")
    migrate(dsn)
    engine = make_engine(dsn)
    seed_clock(engine, load_profile("site_a"))
    yield engine
    engine.dispose()


def count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


def dirty(engine: Engine) -> None:
    """Rows in every kind of table: user input, agent output, audit, the mirror and the sync queue."""
    with engine.begin() as c:
        c.execute(text("INSERT INTO bookmark (user_key, row_key, created_at) VALUES ('pat', 'a|b|1', now())"))
        c.execute(
            text("INSERT INTO feedback (at, user_key, page, message) VALUES (now(), 'pat', '/x', 'hi')")
        )
        c.execute(
            text(
                "INSERT INTO status_log (row_key, status, comment, author_user_key, at) "
                "VALUES ('a|b|1', 'at_risk', 'c', 'pat', now())"
            )
        )
        c.execute(text("INSERT INTO sync_event (source, run_id) VALUES ('webhook', 'r1')"))
        c.execute(text("INSERT INTO watermark (object_name, run_id, synced_at) VALUES ('x', 'r1', now())"))
        c.execute(text("UPDATE demo_clock SET now_utc = now_utc + interval '3 days'"))
        c.execute(
            text(
                "INSERT INTO proposal (agent_key, row_key, kind, payload_json, evidence_json, validator_result_json, status, "
                "required_role, created_at, trace_id) VALUES ('air_gap', 'a|b|1', 'airgap_ticket', '{}', '[]', '[]', "
                "'pending_approval', 'qa_release', now(), 'TR-0001')"
            )
        )
        c.execute(
            text(
                "INSERT INTO action_log (proposal_id, action_type, rendered_json, executed_at) VALUES (1, 't', '{}', now())"
            )
        )
        c.execute(text("SELECT nextval('agent_trace_seq'), nextval('agent_trace_seq')"))
    write_audit(engine, OPENING, "pat", "need_by_set", {})


def test_f13_fr05_every_app_table_is_classified_as_cleared_or_kept(engine: Engine) -> None:
    """A table added by a later feature must be put in one list or the other, on purpose."""
    with engine.connect() as c:
        tables = {
            r[0]
            for r in c.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
        }
    cleared = {t for t in tables if t.startswith(MIRROR_PREFIX)} | set(TRUNCATED)
    assert not cleared & set(KEPT)
    assert tables == cleared | set(KEPT), f"unclassified: {sorted(tables - cleared - set(KEPT))}"
    assert set(TRUNCATED) <= tables and set(KEPT) <= tables


def test_f13_fr05_the_user_table_and_the_migration_version_survive(engine: Engine) -> None:
    assert {"app_user", "alembic_version"} <= set(KEPT)


def test_f13_ac01_a_dirty_database_comes_back_empty_with_users_and_clock_in_place(engine: Engine) -> None:
    dirty(engine)
    users = count(engine, "app_user")
    assert count(engine, "proposal") == 1 and count(engine, "audit_event") == 1
    clear_app_tables(engine)
    seed_after_reset(engine, load_profile("site_a"))
    for table in ("proposal", "action_log", "agent_trace", "audit_event", "bookmark", "feedback",
                  "status_log", "sync_event", "watermark", "override_value"):  # fmt: skip
        assert count(engine, table) == 0, table
    assert count(engine, "filter_preset") == 5 * len(
        load_profile("site_a").demo.presets
    )  # the demo presets, F14
    assert count(engine, "app_user") == users == 5
    with engine.connect() as c:
        clock = c.execute(text("SELECT now_utc, frozen FROM demo_clock")).one()
    assert (clock.now_utc, clock.frozen) == (OPENING, False)
    assert count(engine, "demo_clock") == 1


def test_f13_fr05_ids_and_the_trace_sequence_restart(engine: Engine) -> None:
    dirty(engine)
    clear_app_tables(engine)
    with engine.begin() as c:
        c.execute(text("INSERT INTO sync_event (source) VALUES ('manual')"))
        first_event = c.execute(text("SELECT id FROM sync_event")).scalar_one()
        next_trace = c.execute(text("SELECT nextval('agent_trace_seq')")).scalar_one()
        c.execute(text("DELETE FROM sync_event"))
    assert (first_event, next_trace) == (
        1,
        1,
    )  # OQ-144: proposal and trace ids are the same after every reset


def test_f13_fr05_clearing_twice_is_harmless(engine: Engine) -> None:
    clear_app_tables(engine)
    clear_app_tables(engine)
    seed_after_reset(engine, load_profile("site_a"))
    seed_after_reset(engine, load_profile("site_a"))
    assert count(engine, "demo_clock") == 1


def test_f13_fr05_a_missing_clock_row_is_recreated(engine: Engine) -> None:
    with engine.begin() as c:
        c.execute(text("DELETE FROM demo_clock"))
    seed_after_reset(engine, load_profile("site_a"))
    with engine.connect() as c:
        assert c.execute(text("SELECT now_utc FROM demo_clock")).scalar_one() == OPENING


def test_f13_fr07_the_audit_event_is_written_with_its_details(engine: Engine) -> None:
    clear_app_tables(engine)
    write_audit(engine, OPENING, "admin", "scenario_step", {"step_id": "x", "outcome": "succeeded"})
    with engine.connect() as c:
        row = c.execute(text("SELECT actor_user_key, action, details_json FROM audit_event")).one()
    assert (row.actor_user_key, row.action, row.details_json["outcome"]) == (
        "admin",
        "scenario_step",
        "succeeded",
    )


def test_f14_fr15_every_persona_has_the_demo_presets_after_a_reset_and_twice_is_harmless(
    engine: Engine,
) -> None:
    """OQ-170: the profile's presets are written again by seed_after_reset(), once per persona."""
    profile = load_profile("site_a")
    clear_app_tables(engine)
    seed_after_reset(engine, profile)
    seed_after_reset(engine, profile)
    with engine.connect() as c:
        personas = c.execute(text("SELECT count(*) FROM app_user")).scalar_one()
        rows = c.execute(
            text("SELECT user_key, name, query FROM filter_preset ORDER BY user_key, name")
        ).all()
    wanted = sorted((p.name, p.query) for p in profile.demo.presets)
    assert personas >= 5 and len(wanted) >= 1
    assert len(rows) == personas * len(wanted)
    for user in {r[0] for r in rows}:
        assert sorted((r[1], r[2]) for r in rows if r[0] == user) == wanted
