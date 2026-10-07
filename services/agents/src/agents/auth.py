"""Identity (F12-FR-10, OQ-138): the agents service has no user table.

``X-Demo-User`` is forwarded to app-api's ``/api/me``, which resolves the user and role. A request without the
header is whoever app-api treats as the default persona, exactly as for the app. The role is only ever taken
from that answer, never from the request.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import Engine

from agents.db import write_audit

ME_PATH = "/api/me"


@dataclass(frozen=True)
class Principal:
    user_key: str
    display_name: str
    role: str
    demo_header: str | None  # forwarded on the agent's own reads, so they run as this person


def resolve_principal(client: httpx.Client, demo_header: str | None) -> Principal:
    headers = {"X-Demo-User": demo_header} if demo_header else {}
    try:
        response = client.get(ME_PATH, headers=headers)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"app-api is unreachable: {error}") from error
    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="unknown X-Demo-User")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"app-api returned {response.status_code} for {ME_PATH}")
    body = response.json()
    return Principal(body["user_key"], body["display_name"], body["role"], demo_header)


def current_principal(request: Request, x_demo_user: Annotated[str | None, Header()] = None) -> Principal:
    return resolve_principal(request.app.state.app_client, x_demo_user)


def forbid(request: Request, principal: Principal, roles: tuple[str, ...]) -> None:
    """Refuse: write the ``forbidden`` audit row (own transaction) and raise 403."""
    engine: Engine = request.app.state.engine
    with engine.begin() as connection:
        write_audit(
            connection,
            principal.user_key,
            "forbidden",
            request.path_params.get("row_key"),
            {
                "method": request.method,
                "path": request.url.path,
                "required_roles": list(roles),
                "role": principal.role,
            },
        )
    raise HTTPException(status_code=403, detail=f"requires role {' or '.join(roles)}")


def require_role(*roles: str) -> Callable[[Request, Principal], Principal]:
    """Dependency: the person must hold one of ``roles``; otherwise 403 and a ``forbidden`` audit row."""

    def check(request: Request, principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if principal.role not in roles:
            forbid(request, principal, roles)
        return principal

    return check
