"""Unit tests for api.app.deps — identity headers and role enforcement."""
from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.app.deps import (
    ANALYST,
    ENGINEER,
    PLATFORM_ADMIN,
    CurrentUser,
    get_current_user,
    require_roles,
)

# ---------------------------------------------------------------------------
# Minimal test app that wires up the dependencies
# ---------------------------------------------------------------------------

app = FastAPI()


@app.get("/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return {"subject": user.subject, "roles": user.roles}


@app.get("/analyst-only")
async def analyst_only(user: CurrentUser = require_roles(ANALYST)):
    return {"ok": True}


@app.get("/eng-or-admin")
async def eng_or_admin(user: CurrentUser = require_roles(ENGINEER, PLATFORM_ADMIN)):
    return {"ok": True}

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------


def test_valid_headers_returns_user() -> None:
    resp = client.get("/me", headers={"X-Feanor-Subject": "alice", "X-Feanor-Roles": "analyst"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "alice"
    assert data["roles"] == ["analyst"]


def test_missing_subject_header_returns_401() -> None:
    resp = client.get("/me", headers={"X-Feanor-Roles": "analyst"})
    assert resp.status_code == 401


def test_missing_roles_header_returns_401() -> None:
    resp = client.get("/me", headers={"X-Feanor-Subject": "alice"})
    assert resp.status_code == 401


def test_both_headers_missing_returns_401() -> None:
    resp = client.get("/me")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# require_roles
# ---------------------------------------------------------------------------


def test_correct_role_passes() -> None:
    resp = client.get(
        "/analyst-only",
        headers={"X-Feanor-Subject": "u1", "X-Feanor-Roles": "analyst"},
    )
    assert resp.status_code == 200


def test_wrong_role_returns_403() -> None:
    resp = client.get(
        "/analyst-only",
        headers={"X-Feanor-Subject": "u1", "X-Feanor-Roles": "service_account"},
    )
    assert resp.status_code == 403


def test_any_matching_role_suffices() -> None:
    # engineer should pass eng-or-admin
    resp = client.get(
        "/eng-or-admin",
        headers={"X-Feanor-Subject": "u1", "X-Feanor-Roles": "engineer"},
    )
    assert resp.status_code == 200
    # platform_admin should also pass
    resp2 = client.get(
        "/eng-or-admin",
        headers={"X-Feanor-Subject": "u1", "X-Feanor-Roles": "platform_admin"},
    )
    assert resp2.status_code == 200


def test_multiple_roles_header_parsed_correctly() -> None:
    resp = client.get(
        "/eng-or-admin",
        headers={"X-Feanor-Subject": "u1", "X-Feanor-Roles": "analyst,engineer"},
    )
    assert resp.status_code == 200
