"""The ``notify`` step: tell the app that a new contract is published (F07-FR-04, OQ-049).

The body is compact JSON and is sent as the exact bytes that are signed (HMAC-SHA256 with ``WEBHOOK_SECRET``,
header ``X-Signature: sha256=<hex>``). Network errors and 5xx answers are retried after 1 s, 2 s and 4 s; 4xx
answers are not. The outcome is ``ok``, ``failed`` or ``skipped`` (no ``WEBHOOK_URL``) and **never fails the
run**: the data is published either way, and the app's own safety net picks it up.
"""

import hashlib
import hmac
import json
import logging
import os
import time
from collections.abc import Callable

import httpx

from r2r_pipeline.context import RunContext
from r2r_pipeline.lake import read_delta
from r2r_pipeline.runlog import StepResult

log = logging.getLogger(__name__)

RETRY_DELAYS = (1.0, 2.0, 4.0)
TIMEOUT_SECONDS = 10.0


def sign(secret: str, body: bytes) -> str:
    """The ``X-Signature`` header value for ``body``."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def webhook_body(ctx: RunContext) -> bytes:
    """``{"run_id", "published_at"}`` from the published status, as compact JSON bytes."""
    [status] = read_delta(ctx.lake_root, "published.pipeline_status_v").to_pylist()
    payload = {"run_id": status["last_run_id"], "published_at": status["last_success_at"].isoformat()}
    return json.dumps(payload, separators=(",", ":")).encode()


def _attempt(client: httpx.Client, url: str, body: bytes, secret: str) -> tuple[bool, bool, str]:
    """``(ok, retryable, error)`` of one POST."""
    headers = {"Content-Type": "application/json", "X-Signature": sign(secret, body)}
    try:
        response = client.post(url, content=body, headers=headers)
    except httpx.TransportError as error:
        return False, True, f"{type(error).__name__}: {error}"
    if response.is_success:
        return True, False, ""
    return False, response.status_code >= 500, f"HTTP {response.status_code}"


def notify(
    ctx: RunContext,
    *,
    url: str | None = None,
    secret: str | None = None,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    delays: tuple[float, ...] = RETRY_DELAYS,
) -> StepResult:
    url = os.environ.get("WEBHOOK_URL", "") if url is None else url
    secret = os.environ.get("WEBHOOK_SECRET", "") if secret is None else secret
    if not url:
        return StepResult(notify_status="skipped", detail={"reason": "WEBHOOK_URL is not set"})
    if not secret:
        log.warning("notify: WEBHOOK_SECRET is not set; the webhook was not sent")
        return StepResult(
            notify_status="failed", detail={"attempts": 0, "error": "WEBHOOK_SECRET is not set"}
        )
    body = webhook_body(ctx)
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS)
    error, attempts = "", 0
    try:
        for attempt in range(len(delays) + 1):
            attempts += 1
            ok, retryable, error = _attempt(http, url, body, secret)
            if ok:
                return StepResult(notify_status="ok", detail={"attempts": attempts})
            if not retryable or attempt == len(delays):
                break
            sleep(delays[attempt])
    finally:
        if client is None:
            http.close()
    log.warning("notify: webhook failed after %d attempt(s): %s", attempts, error)
    return StepResult(notify_status="failed", detail={"attempts": attempts, "error": error})
