"""The demo reset (F13-FR-05): back to the demo-start state, the same way every time.

Order: pause the agents autorun, take the sync lock (the drain worker then skips its passes), clear the app
tables, put the clock back, wipe the lakehouse, regenerate the source data, run the pipeline, let go of the
lock, wait until the app has synced, resume the autorun. A failure still lets go of the lock and resumes the
autorun. The reset clears the audit log, so it does not write an audit row of its own.

The generator runs as a child process of this service: it fixes the demo clock per event, and that must not
touch the clock this service answers requests with.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from r2r_core.profile import SiteProfile
from r2r_core.sync_lock import RESET_LOCK_KEY
from sqlalchemy import Engine, text

from scenario.clock_api import reset_clock
from scenario.gateway import CallFailed, Gateway
from scenario.pipeline_api import DagsterClient, wait_for_run
from scenario.runner import PIPELINE_TIMEOUT_SECONDS, SYNC_TIMEOUT_SECONDS, Run, RunRegistry, wait_for_sync

DATAGEN_TIMEOUT_SECONDS = 600
RESET_JOB = "r2r_reset_lakehouse"
PIPELINE_JOB = "r2r_pipeline"

# Every table of the app database is in exactly one list; a test compares them with information_schema, so a
# table added by a later feature has to be classified on purpose (OQ-148).
MIRROR_PREFIX = "mirror_"  # the copies of the published contract: the sync fills them again
TRUNCATED = (
    "action_log", "agent_trace", "audit_event", "bookmark", "comment", "feedback", "filter_preset",
    "override_value", "proposal", "status_log", "sync_event", "watermark",
)  # fmt: skip
# `app_user` and `alembic_version` as the spec says; `demo_clock` is reset in place; the heartbeat belongs to
# the worker, which writes it every two seconds.
KEPT = ("alembic_version", "app_user", "demo_clock", "worker_heartbeat")
TRACE_SEQUENCE = "agent_trace_seq"


def clear_app_tables(engine: Engine) -> None:
    """One ``TRUNCATE`` over every cleared table: ids restart and the ``action_log`` foreign key is fine."""
    with engine.begin() as connection:
        mirrors = connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name LIKE :p"
            ),
            {"p": MIRROR_PREFIX.replace("_", r"\_") + "%"},
        ).scalars()
        names = ", ".join([*TRUNCATED, *sorted(mirrors)])
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY"))
        connection.execute(text(f"ALTER SEQUENCE {TRACE_SEQUENCE} RESTART WITH 1"))


def seed_after_reset(engine: Engine, profile: SiteProfile) -> None:
    """What a reset puts back: the clock row, updated in place, and the demo presets of every persona.

    No migration seeds a cleared table, so the profile's ``demo.presets`` are written again here (F14-FR-15,
    OQ-170), stamped with the demo clock's opening time.
    """
    reset_clock(engine, profile)
    if not profile.demo.presets:
        return
    with engine.begin() as connection:
        for preset in profile.demo.presets:
            connection.execute(
                text(
                    "INSERT INTO filter_preset (user_key, name, query, created_at) "
                    "SELECT user_key, :name, :query, :at FROM app_user "
                    "ON CONFLICT (user_key, name) DO UPDATE SET query = EXCLUDED.query"
                ),
                {"name": preset.name, "query": preset.query, "at": profile.demo.start_datetime},
            )


@contextmanager
def hold_sync_lock(engine: Engine) -> Iterator[None]:
    """Exclusive, for one transaction that touches no table, so the app keeps answering reads."""
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": RESET_LOCK_KEY})
        try:
            yield
        finally:
            connection.rollback()


def run_command(command: list[str]) -> tuple[int, str]:
    done = subprocess.run(
        command, capture_output=True, text=True, timeout=DATAGEN_TIMEOUT_SECONDS, check=False
    )
    return done.returncode, (done.stdout + done.stderr).strip()


class Reset:
    def __init__(
        self,
        engine: Engine,
        profile: SiteProfile,
        gateway: Gateway,
        dagster: Callable[[], DagsterClient],
        registry: RunRegistry,
        run_command: Callable[[list[str]], tuple[int, str]] = run_command,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.engine = engine
        self.profile = profile
        self.gateway = gateway
        self.dagster = dagster
        self.registry = registry
        self.run_command = run_command
        self.sleep = sleep

    def start(self, actor: str = "system", wait: bool = False) -> Run:
        run = self.registry.begin("reset", "demo", actor)
        run.emit("start", "Reset the demo to its starting state")
        thread = threading.Thread(target=self._execute, args=(run,), name="demo-reset", daemon=True)
        thread.start()
        if wait:
            thread.join()
        return run

    def _execute(self, run: Run) -> None:
        paused = self._autorun(run, "pause")
        failure: Exception | None = None
        try:
            pipeline_run_id = self._rebuild(run)
            self._phase(run, "Wait for the app to sync")
            wait_for_sync(self.gateway, pipeline_run_id, self.sleep, SYNC_TIMEOUT_SECONDS)
            run.emit("action_done", f"the app has synced run {pipeline_run_id}")
        except Exception as error:  # the run must always end, or the page would wait for ever
            failure = error
        if paused or failure is None:
            self._autorun(run, "resume")
        if failure is not None:
            run.finish("failed", f"reset failed: {failure}")
        else:
            run.finish("succeeded", self._health())

    def _rebuild(self, run: Run) -> str:
        """Everything that happens while the drain worker is held back. Returns the pipeline run id."""
        with hold_sync_lock(self.engine):
            run.emit("line", "sync lock taken: the drain worker pauses until the new data is published")
            self._phase(run, "Clear the app tables and put the demo clock back")
            clear_app_tables(self.engine)
            seed_after_reset(self.engine, self.profile)
            run.emit("action_done", "tables cleared, ids and the trace sequence restarted")
            client = self.dagster()
            self._phase(run, "Wipe the lakehouse")
            self._dagster_job(client, RESET_JOB, run)
            self._phase(run, "Regenerate the source data")
            self._datagen(run)
            self._phase(run, "Run the pipeline")
            return self._dagster_job(client, PIPELINE_JOB, run)

    def _phase(self, run: Run, label: str) -> None:
        run.emit("action_start", label)

    def _dagster_job(self, client: DagsterClient, job: str, run: Run) -> str:
        run_id = client.launch(job)
        status = wait_for_run(client, run_id, PIPELINE_TIMEOUT_SECONDS, self.sleep)
        if status != "SUCCESS":
            raise CallFailed(f"the Dagster job {job} (run {run_id}) ended {status}")
        run.emit("action_done", f"{job} succeeded (run {run_id})")
        return run_id

    def _datagen(self, run: Run) -> None:
        site = os.environ.get("SITE_PROFILE", "site_a")
        with tempfile.TemporaryDirectory() as artifacts:
            command = [
                sys.executable,
                "-m",
                "datagen",
                "generate",
                "--profile",
                site,
                "--artifacts",
                artifacts,
            ]
            code, output = self.run_command(command)
        last = output.splitlines()[-1] if output else ""
        if code != 0:
            raise CallFailed(f"datagen failed (exit {code}): {last}")
        run.emit("action_done", last or "source data regenerated")

    def _autorun(self, run: Run, action: str) -> bool:
        """Pause or resume the agents autorun. An agents service that is down is a warning, not a failure."""
        try:
            self.gateway.call("agents", "POST", f"/agents/autorun/{action}")
        except CallFailed as error:
            run.emit("line", f"warning: could not {action} the agents autorun: {error}")
            return False
        run.emit("line", f"agents autorun {action}d")
        return True

    def _health(self) -> str:
        overview = self.gateway.call("app", "GET", "/api/overview", user="admin")
        air_gaps = sum(1 for row in overview["rows"] if row.get("air_gap"))
        try:
            proposals = len(self.gateway.call("agents", "GET", "/proposals", user="admin")["rows"])
        except CallFailed:
            proposals = 0
        count = overview.get("batch_count", len(overview["rows"]))
        gaps = f"{air_gaps} air gap{'' if air_gaps == 1 else 's'}"
        return f"Demo reset: {len(overview['rows'])} rows ({count} batches), {gaps}, {proposals} proposals"
