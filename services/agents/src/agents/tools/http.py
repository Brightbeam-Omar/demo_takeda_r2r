"""The only way the agents service reaches other systems: GET, to an allow-listed host (F12-FR-01, F12-FR-04).

There is no ``post`` or ``put`` here on purpose. Each source has a name and a base URL from the settings;
a request to anything else is refused before it leaves the process.
"""

from typing import Any
from urllib.parse import urlsplit

import httpx

from agents.settings import Settings


class ToolError(Exception):
    """A tool call that cannot be answered (unknown record, source down, refused). Safe to show the model."""


class NotFound(ToolError):
    """The record does not exist in the source."""


class ReadOnlyHttp:
    def __init__(self, bases: dict[str, str], *, transport: httpx.BaseTransport | None = None) -> None:
        self._bases = {name: base.rstrip("/") for name, base in bases.items()}
        self._allowed_hosts = {urlsplit(base).netloc for base in self._bases.values()}
        self._client = httpx.Client(timeout=10, transport=transport)

    @classmethod
    def from_settings(
        cls, settings: Settings, *, transport: httpx.BaseTransport | None = None
    ) -> "ReadOnlyHttp":
        return cls(
            {
                "app": settings.app_api_url,
                "erp": settings.erp_url,
                "lims": settings.lims_url,
                "qms": settings.qms_url,
            },
            transport=transport,
        )

    def get_json(
        self, system: str, path: str, *, params: dict[str, str] | None = None, demo_user: str | None = None
    ) -> Any:
        base = self._bases.get(system)
        if base is None:
            raise ToolError(f"unknown system {system!r}")
        url = f"{base}{path}"
        if urlsplit(url).netloc not in self._allowed_hosts:
            raise ToolError(f"host not allowed for {system}")
        headers = {"X-Demo-User": demo_user} if demo_user else {}
        try:
            response = self._client.get(url, params=params, headers=headers)
        except httpx.HTTPError as error:
            raise ToolError(f"{system} is unreachable ({type(error).__name__})") from None
        if response.status_code == 404:
            raise NotFound(f"{system} has no record at {path}")
        if response.status_code != 200:
            raise ToolError(f"{system} answered {response.status_code} for {path}")
        return response.json()
