"""Demo identity (ADR-005): ``X-Demo-User`` names an ``app_user`` row, honoured only with ``DEMO_MODE=true``.

This is the minimal check F08's admin-only endpoint needs. F09 extends it (the full permission matrix, and the
``AuthProvider`` interface that an OIDC proxy replaces in Tier 2).
"""

import os
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app_api.db import get_session
from app_api.models import AppUser


def current_user(
    session: Annotated[Session, Depends(get_session)],
    x_demo_user: Annotated[str | None, Header()] = None,
) -> AppUser:
    if os.environ.get("DEMO_MODE", "").lower() != "true":
        raise HTTPException(status_code=401, detail="no identity provider is configured")
    user = session.get(AppUser, x_demo_user) if x_demo_user else None
    if user is None:
        raise HTTPException(status_code=401, detail="unknown or missing X-Demo-User")
    return user


def require_role(*roles: str) -> Callable[[AppUser], AppUser]:
    """Dependency: the current user must hold one of ``roles`` (403 otherwise)."""

    def check(user: Annotated[AppUser, Depends(current_user)]) -> AppUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"requires role {' or '.join(roles)}")
        return user

    return check
