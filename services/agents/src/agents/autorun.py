"""Optional autorun (F12-FR-11, FR-14): run the air-gap agent after each sync that brings a new contract run.

Off by default (the presenter clicks Run). With ``AGENTS_AUTORUN=true`` a background thread polls
``/api/sync/status`` every 30 s and, when the mirrored run changes, runs the agent for the air-gap rows that
have **never** had a proposal (so a rejected proposal is not proposed again on every run, OQ-137). It reads
app-api as ``AGENTS_SERVICE_USER``. The demo reset pauses it before wiping and resumes it after the sync;
``resume`` sets the cursor to the run that is current then, so the first poll after a reset does not run the
agent on the freshly seeded state.
"""

import logging
import threading
from dataclasses import dataclass

from agents.air_gap import agent as air_gap_agent
from agents.deps import Deps
from agents.tools.http import ToolError

POLL_SECONDS = 30.0
WATERMARK_OBJECT = "batch_pipeline_v"
log = logging.getLogger("agents.autorun")


@dataclass
class AutorunState:
    enabled: bool
    paused: bool
    cursor: str | None


class Autorun:
    def __init__(self, deps: Deps, *, enabled: bool) -> None:
        self.deps = deps
        self.enabled = enabled
        self.paused = False
        self.cursor: str | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def state(self) -> AutorunState:
        return AutorunState(self.enabled, self.paused, self.cursor)

    def current_run(self) -> str | None:
        """The run id the app has mirrored (the ``batch_pipeline_v`` watermark), or None if unreadable."""
        body = self.deps.http.get_json("app", "/api/sync/status", demo_user=self.deps.settings.service_user)
        for mark in body.get("watermarks", []):
            if mark.get("object_name") == WATERMARK_OBJECT:
                return str(mark["run_id"])
        return None

    def tick(self) -> air_gap_agent.RunSummary | None:
        """One poll. Returns the run summary when a run happened."""
        with self._lock:
            if not self.enabled or self.paused:
                return None
            try:
                run_id = self.current_run()
            except ToolError as error:
                log.warning("autorun: cannot read the sync status: %s", error)
                return None
            if run_id is None:
                return None
            if self.cursor is None:  # first look: remember the state, do not act on it
                self.cursor = run_id
                return None
            if run_id == self.cursor:
                return None
            self.cursor = run_id
            try:
                summary = air_gap_agent.run(self.deps, None, autorun=True)
            except ToolError as error:
                log.warning("autorun: the run failed: %s", error)
                return None
            log.info(
                "autorun: run %s created %d proposal(s), %d skipped, %d error(s)",
                run_id,
                len(summary.of("created")),
                len(summary.of("skipped")),
                len(summary.of("error")),
            )
            return summary

    def pause(self) -> AutorunState:
        with self._lock:
            self.paused = True
        return self.state()

    def resume(self) -> AutorunState:
        with self._lock:
            try:
                self.cursor = self.current_run()
            except ToolError:
                self.cursor = None  # the next poll takes the state it finds as the starting point
            self.paused = False
        return self.state()

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="agents-autorun", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(POLL_SECONDS):
            try:
                self.tick()
            except Exception:  # a failed poll must never end the loop
                log.exception("autorun: unexpected error")
