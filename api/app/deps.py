"""FastAPI dependencies for identity and role enforcement."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

# Keycloak role constants — must match realm role names exactly.
PLATFORM_ADMIN = "platform_admin"
ENGINEER = "engineer"
ANALYST = "analyst"
SERVICE_ACCOUNT = "service_account"


class CurrentUser(BaseModel):
    subject: str
    roles: list[str]


async def get_current_user(
    x_feanor_subject: str | None = Header(None, alias="X-Feanor-Subject"),
    x_feanor_roles: str | None = Header(None, alias="X-Feanor-Roles"),
) -> CurrentUser:
    if x_feanor_subject is None or x_feanor_roles is None:
        raise HTTPException(status_code=401, detail="missing identity headers")
    roles = [r.strip() for r in x_feanor_roles.split(",") if r.strip()]
    return CurrentUser(subject=x_feanor_subject, roles=roles)


def require_roles(*roles: str) -> Callable:
    """Return a FastAPI dependency that enforces the caller holds at least one of *roles*."""

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(r in user.roles for r in roles):
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return Depends(_check)
