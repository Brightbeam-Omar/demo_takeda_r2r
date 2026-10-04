"""Structured JSON logs (02-architecture section 8): one line per record with ``service``, ``run_id``,
``event_id``, ``trace_id`` and any ``extra`` fields such as ``duration_ms``.

``bind(event_id=..., run_id=...)`` adds ids to every record logged inside the block, so the sync code does not
pass them around.
"""

import contextlib
import contextvars
import json
import logging
import sys
from collections.abc import Iterator
from typing import Any

_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("log_context", default={})  # noqa: B039

# Record attributes that belong to the logging module, not to the line we print.
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "taskName"}


@contextlib.contextmanager
def bind(**fields: Any) -> Iterator[None]:
    token = _context.set({**_context.get(), **fields})
    try:
        yield
    finally:
        _context.reset(token)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "service": self.service,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        line.update(_context.get())
        line.update({k: v for k, v in vars(record).items() if k not in _STANDARD})
        if record.exc_info:
            line["error"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


def configure_logging(service: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger("app_api")
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False
