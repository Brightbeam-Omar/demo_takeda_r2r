"""F08-FR-02 and FR-11: the webhook. Covers F08-AC-02, AC-07 and AC-09."""

import hashlib
import hmac
import json
import subprocess
import sys
import time
from typing import Any

import pytest
from app_api.sync.webhook import verify_signature
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

SECRET = "test-webhook-secret"


@pytest.fixture(autouse=True)
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBHOOK_SECRET", SECRET)


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post(client: TestClient, body: bytes, signature: str | None) -> Any:
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Signature"] = signature
    return client.post("/api/sync/webhook", content=body, headers=headers)


def rows(factory: sessionmaker[Session], query: str) -> list[Any]:
    with factory() as session:
        return list(session.execute(text(query)).all())


BODY = json.dumps(
    {"run_id": "run-abc", "published_at": "2026-10-12T07:00:00+00:00"}, separators=(",", ":")
).encode()


def test_f08_fr02_verify_signature_accepts_only_the_exact_hmac_of_the_raw_body() -> None:
    assert verify_signature(SECRET, BODY, sign(BODY))
    assert not verify_signature(SECRET, BODY + b" ", sign(BODY))
    assert not verify_signature(SECRET, BODY, sign(BODY, "other-secret"))
    assert not verify_signature(SECRET, BODY, sign(BODY).replace("sha256=", ""))
    assert not verify_signature(SECRET, BODY, None)
    assert not verify_signature("", BODY, sign(BODY, ""))  # an unset secret rejects everything


def test_f08_fr02_verify_signature_uses_a_constant_time_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def spy(a: bytes, b: bytes) -> bool:
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr("app_api.sync.webhook.hmac.compare_digest", spy)
    verify_signature(SECRET, BODY, sign(BODY))
    assert len(calls) == 1


@pytest.mark.integration
def test_f08_fr02_valid_signature_queues_a_pending_event_and_returns_202(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    response = post(client, BODY, sign(BODY))
    assert response.status_code == 202
    event_id = response.json()["event_id"]
    [row] = rows(app_factory, "SELECT id, source, run_id, status, claimed_at FROM sync_event")
    assert tuple(row) == (event_id, "webhook", "run-abc", "pending", None)
    assert rows(app_factory, "SELECT 1 FROM audit_event") == []


@pytest.mark.integration
@pytest.mark.parametrize("signature", [None, "sha256=deadbeef", "garbage"])
def test_f08_ac02_bad_signature_gives_401_no_event_and_one_audit_row(
    client: TestClient, app_factory: sessionmaker[Session], signature: str | None
) -> None:
    response = post(client, BODY, signature)
    assert response.status_code == 401
    assert rows(app_factory, "SELECT 1 FROM sync_event") == []
    [audit] = rows(app_factory, "SELECT action, actor_user_key, details_json FROM audit_event")
    assert audit[0] == "webhook_rejected"
    assert audit[1] == "system"
    assert audit[2]["reason"] == "bad_signature"


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload", [b"not json", b"[]", b'{"published_at":"x"}', b'{"run_id":""}', b'{"run_id":5}']
)
def test_f08_ac09_signed_but_malformed_body_gives_422_no_event_and_one_audit_row(
    client: TestClient, app_factory: sessionmaker[Session], payload: bytes
) -> None:
    response = post(client, payload, sign(payload))
    assert response.status_code == 422
    assert rows(app_factory, "SELECT 1 FROM sync_event") == []
    [audit] = rows(app_factory, "SELECT action, details_json FROM audit_event")
    assert audit[0] == "webhook_rejected"
    assert audit[1]["reason"] == "invalid_body"


@pytest.mark.integration
def test_f08_fr11_oversized_body_is_refused_before_it_is_parsed(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    payload = b'{"run_id":"' + b"x" * (1024 * 1024) + b'"}'
    response = post(client, payload, sign(payload))
    assert response.status_code == 413
    assert rows(app_factory, "SELECT 1 FROM sync_event") == []


@pytest.mark.integration
def test_f08_fr02_the_audit_row_uses_the_demo_clock(
    client: TestClient, app_factory: sessionmaker[Session]
) -> None:
    post(client, BODY, "sha256=bad")
    [(at,)] = rows(app_factory, "SELECT at FROM audit_event")
    assert at.isoformat() == "2026-10-12T07:00:00+00:00"


def test_f08_ac07_importing_the_api_does_not_load_the_lakehouse_reader() -> None:
    code = (
        "import sys, app_api.main, app_api.sync.webhook;"
        "bad = [m for m in ('deltalake', 'pyarrow', 'r2r_core.contract') if m in sys.modules];"
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.integration
def test_f08_fr02_p95_latency_is_under_100_ms(client: TestClient) -> None:
    post(client, BODY, sign(BODY))  # warm up
    durations = []
    for _ in range(60):
        began = time.perf_counter()
        assert post(client, BODY, sign(BODY)).status_code == 202
        durations.append(time.perf_counter() - began)
    durations.sort()
    assert durations[int(len(durations) * 0.95)] < 0.1
