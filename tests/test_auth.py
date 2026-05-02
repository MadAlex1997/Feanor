"""Unit tests for feanor.auth — TokenManager credential resolution and refresh."""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from feanor.config import Profile, _DEFAULT_LOCAL
from feanor.auth import TokenManager


def _make_profile(**kwargs) -> Profile:
    return Profile(name="local", **{**_DEFAULT_LOCAL, **kwargs})


def _make_jwt(exp: float) -> str:
    """Craft a minimal JWT with the given exp claim (no valid signature)."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload_bytes = json.dumps({"sub": "u1", "exp": int(exp)}).encode()
    payload = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


# ---------------------------------------------------------------------------
# Strategy 1: FEANOR_TOKEN
# ---------------------------------------------------------------------------

def test_feanor_token_env_returned_directly(monkeypatch):
    monkeypatch.setenv("FEANOR_TOKEN", "my-static-token")
    monkeypatch.delenv("FEANOR_CLIENT_ID", raising=False)
    tm = TokenManager(_make_profile())
    assert tm.get_token() == "my-static-token"


def test_feanor_token_near_expiry_logs_warning(monkeypatch, caplog):
    expired_token = _make_jwt(time.time() - 10)
    monkeypatch.setenv("FEANOR_TOKEN", expired_token)
    monkeypatch.delenv("FEANOR_CLIENT_ID", raising=False)

    import logging
    with caplog.at_level(logging.WARNING, logger="feanor.auth"):
        tm = TokenManager(_make_profile())
        result = tm.get_token()

    assert result == expired_token
    assert "expired" in caplog.text.lower() or "expiry" in caplog.text.lower()


# ---------------------------------------------------------------------------
# Strategy 2: client credentials
# ---------------------------------------------------------------------------

def test_client_credentials_flow(monkeypatch):
    monkeypatch.delenv("FEANOR_TOKEN", raising=False)
    monkeypatch.setenv("FEANOR_CLIENT_ID", "svc-id")
    monkeypatch.setenv("FEANOR_CLIENT_SECRET", "svc-secret")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": "cc-token"}
    mock_resp.raise_for_status = MagicMock()

    with patch("feanor.auth.httpx.post", return_value=mock_resp) as mock_post:
        tm = TokenManager(_make_profile())
        token = tm.get_token()

    assert token == "cc-token"
    call_kwargs = mock_post.call_args
    assert "client_credentials" in str(call_kwargs)


# ---------------------------------------------------------------------------
# Strategy 3: cached token still valid → no HTTP call
# ---------------------------------------------------------------------------

def test_cached_valid_token_returned_without_request(monkeypatch):
    monkeypatch.delenv("FEANOR_TOKEN", raising=False)
    monkeypatch.delenv("FEANOR_CLIENT_ID", raising=False)

    future_token = _make_jwt(time.time() + 3600)
    profile = _make_profile(token=future_token)

    with patch("feanor.auth.httpx.post") as mock_post:
        tm = TokenManager(profile)
        token = tm.get_token()

    assert token == future_token
    mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Strategy 3: cached token near expiry → refresh
# ---------------------------------------------------------------------------

def test_refresh_flow_triggered_when_token_near_expiry(monkeypatch):
    monkeypatch.delenv("FEANOR_TOKEN", raising=False)
    monkeypatch.delenv("FEANOR_CLIENT_ID", raising=False)

    stale_token = _make_jwt(time.time() + 10)  # within buffer
    new_token = _make_jwt(time.time() + 3600)
    profile = _make_profile(token=stale_token, refresh_token="refresh-tok")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": new_token,
        "refresh_token": "new-refresh",
        "expires_in": 900,
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("feanor.auth.httpx.post", return_value=mock_resp):
        with patch("feanor.config.save_config"):
            tm = TokenManager(profile)
            token = tm.get_token()

    assert token == new_token
