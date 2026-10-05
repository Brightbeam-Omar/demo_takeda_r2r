"""Demo identity (ADR-005): ``X-Demo-User`` names an ``app_user`` row, honoured only with ``DEMO_MODE=true``.

A request without the header is ``pat`` (the planner persona the demo opens as). Outside demo mode the header
is rejected: Tier 2 replaces this module with an ``AuthProvider`` behind an OIDC proxy (F09-FR-05).
"""

import os
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from r2r_core import clock
from sqlalchemy.orm import Session, sessionmaker

from app_api.db import get_session
from app_api.models import AppUser, AuditEvent

DEFAULT_USER = "pat"


def demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "").lower() == "true"


def current_user(
    session: Annotated[Session, Depends(get_session)],
    x_demo_user: Annotated[str | None, Header()] = None,
) -> AppUser:
    if not demo_mode():
        raise HTTPException(status_code=401, detail="no identity provider is configured")
    user = session.get(AppUser, x_demo_user or DEFAULT_USER)
    if user is None:
        raise HTTPException(status_code=401, detail="unknown X-Demo-User")
    return user


def _audit_forbidden(session: Session, request: Request, user: AppUser, roles: tuple[str, ...]) -> None:
    """Write the ``forbidden`` audit row in its own transaction (the failing request rolls back)."""
    with sessionmaker(session.get_bind())() as audit_session:
        audit_session.add(
            AuditEvent(
                at=clock.now(),
                actor_user_key=user.user_key,
                action="forbidden",
                row_key=request.path_params.get("row_key"),
                details_json={
                    "method": request.method,
                    "path": request.url.path,
                    "required_roles": list(roles),
                    "role": user.role,
                },
            )
        )
        audit_session.commit()


def require_role(*roles: str) -> Callable[[Request, Session, AppUser], AppUser]:
    """Dependency: the user must hold one of ``roles``; otherwise 403 and a ``forbidden`` audit row."""

    def check(
        request: Request,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AppUser, Depends(current_user)],
    ) -> AppUser:
        if user.role not in roles:
            _audit_forbidden(session, request, user, roles)
            raise HTTPException(status_code=403, detail=f"requires role {' or '.join(roles)}")
        return user

    return check
