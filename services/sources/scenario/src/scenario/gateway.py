"""The HTTP calls a step makes: the three source simulators, the application API and the agents service.

One place holds the base URLs, the scenario token and the ``X-Demo-User`` header, so a step only names a
service, a path and (optionally) the user it acts as. Tests give it an ``httpx`` mock transport.
"""

import os
from dataclasses import dataclass
from typing import Any

import httpx

SOURCE_SERVICES = ("erp", "lims", "qms")


class CallFailed(RuntimeError):
    """A service answered with an error, or could not be reached."""


@dataclass(frozen=True)
class Endpoints:
    app: str
    erp: str
    lims: str
    qms: str
    agents: str

    @staticmethod
    def from_env() -> "Endpoints":
        env = os.environ
        return Endpoints(
            app=env.get("APP_API_URL", "http://app-api:8000"),
            erp=env.get("ERP_URL", "http://erp-sim:8101"),
            lims=env.get("LIMS_URL", "http://lims-sim:8102"),
            qms=env.get("QMS_URL", "http://qms-sim:8103"),
            agents=env.get("AGENTS_URL", "http://agents:8200"),
        )


class Gateway:
    def __init__(
        self, endpoints: Endpoints, token: str | None = None, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.endpoints = endpoints
        self.token = os.environ.get("SCENARIO_TOKEN", "") if token is None else token
        self._http = httpx.Client(transport=transport, timeout=60.0)

    def base(self, service: str) -> str:
        return str(getattr(self.endpoints, service))

    def call(
        self,
        service: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        user: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Returns the JSON answer. Sources and the autorun endpoints need the scenario token; the app and the
        agents API take ``X-Demo-User`` (OQ-150)."""
        headers = {"X-Scenario-Token": self.token}
        if user is not None:
            headers["X-Demo-User"] = user
        try:
            response = self._http.request(
                method, self.base(service) + path, json=body, headers=headers, params=params
            )
        except httpx.HTTPError as error:
            raise CallFailed(f"{service} is not reachable: {error}") from error
        if response.status_code >= 400:
            raise CallFailed(
                f"{service} {method} {path} answered {response.status_code}: {_detail(response)}"
            )
        return response.json() if response.content else None

    def get(self, service: str, path: str, **params: Any) -> Any:
        return self.call(service, "GET", path, params=params or None)


def _detail(response: httpx.Response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except (ValueError, AttributeError):
        detail = response.text
    return str(detail)[:300]
