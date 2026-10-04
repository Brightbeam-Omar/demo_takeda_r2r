"""T5 [TDD]: notify with an HMAC signature and retry (F07-FR-04, F07-AC-06)."""

import hashlib
import hmac
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
from fixture_world import World
from r2r_core.profile import SiteProfile
from r2r_pipeline.context import RunContext
from r2r_pipeline.notify import notify, sign
from r2r_pipeline.publish import publish
from r2r_pipeline.runlog import StepResult, run_step
from r2r_pipeline.setup import setup
from r2r_pipeline.snapshot import snapshot_aggregate
from r2r_pipeline.transform import transform

SECRET = "test-secret"
URL = "http://app.test/api/sync/webhook"
PUBLISHED_AT = datetime(2026, 10, 12, 7, 0, tzinfo=UTC)


@pytest.fixture
def published(tmp_path: Path, profile: SiteProfile, demo_clock: None) -> RunContext:
    world = World()
    world.receive("B1", "10000001", datetime(2026, 10, 1).date())
    ctx = setup(profile, tmp_path, run_id="run-7")
    world.write(tmp_path)
    run_step(ctx, "extract", lambda: StepResult(detail={"freshness": {}}))
    run_step(ctx, "transform", lambda: (transform(ctx), StepResult())[1])
    run_step(ctx, "snapshot_aggregate", lambda: snapshot_aggregate(ctx))
    run_step(ctx, "publish", lambda: publish(ctx))
    return ctx


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_f07_fr04_the_signature_is_the_sha256_hmac_of_the_exact_bytes() -> None:
    body = b'{"run_id":"r","published_at":"x"}'
    expected = "sha256=" + hmac.new(b"k", body, hashlib.sha256).hexdigest()
    assert sign("k", body) == expected


def test_f07_ac06_a_test_server_verifies_the_signed_body(published: RunContext) -> None:
    received: list[tuple[bytes, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append((body, self.headers["X-Signature"]))
            self.send_response(202)
            self.end_headers()

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = notify(published, url=f"http://127.0.0.1:{server.server_port}/hook", secret=SECRET)
    finally:
        server.shutdown()
        server.server_close()
    assert result.notify_status == "ok"
    [(body, signature)] = received
    assert signature == "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert json.loads(body) == {"run_id": "run-7", "published_at": PUBLISHED_AT.isoformat()}
    assert b" " not in body  # compact JSON


def test_f07_fr04_the_body_is_the_signed_bytes(published: RunContext) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202)

    notify(published, url=URL, secret=SECRET, client=client_for(handler))
    [request] = seen
    assert request.headers["X-Signature"] == sign(SECRET, request.content)
    assert request.headers["Content-Type"] == "application/json"


def test_f07_oq049_network_errors_are_retried_after_one_two_and_four_seconds(published: RunContext) -> None:
    calls: list[int] = []
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 4:
            raise httpx.ConnectError("refused")
        return httpx.Response(202)

    result = notify(published, url=URL, secret=SECRET, client=client_for(handler), sleep=slept.append)
    assert (result.notify_status, len(calls), slept) == ("ok", 4, [1, 2, 4])


def test_f07_oq049_server_errors_are_retried_then_reported_failed(published: RunContext) -> None:
    calls: list[int] = []
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    result = notify(published, url=URL, secret=SECRET, client=client_for(handler), sleep=slept.append)
    assert (result.notify_status, len(calls), slept) == ("failed", 4, [1, 2, 4])
    assert result.detail["attempts"] == 4
    assert "503" in result.detail["error"]


def test_f07_oq049_client_errors_are_not_retried(published: RunContext) -> None:
    calls: list[int] = []
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(401)

    result = notify(published, url=URL, secret=SECRET, client=client_for(handler), sleep=slept.append)
    assert (result.notify_status, len(calls), slept) == ("failed", 1, [])


def test_f07_oq049_no_webhook_url_is_skipped(published: RunContext) -> None:
    result = notify(published, url="", secret=SECRET)
    assert result.notify_status == "skipped"


def test_f07_fr04_a_missing_secret_is_a_failed_notification_not_a_failed_run(published: RunContext) -> None:
    result = notify(published, url=URL, secret="")
    assert result.notify_status == "failed"
    assert "WEBHOOK_SECRET" in result.detail["error"]


def test_f07_fr04_the_outcome_is_recorded_in_the_run_log(published: RunContext) -> None:
    from r2r_pipeline.runlog import step_row

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    run_step(
        published,
        "notify",
        lambda: notify(published, url=URL, secret=SECRET, client=client_for(handler), sleep=lambda s: None),
    )
    row = step_row(published, "notify")
    assert (row["status"], row["notify_status"]) == ("success", "failed")  # the run itself is not failed
