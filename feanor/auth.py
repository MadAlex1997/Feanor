"""TokenManager — credential acquisition, caching, and refresh.

Resolution order (highest to lowest priority):
  1. FEANOR_TOKEN env var — used as-is, no refresh.
  2. FEANOR_CLIENT_ID + FEANOR_CLIENT_SECRET — client credentials grant.
  3. Cached token in ~/.feanor/config.yaml (profile-scoped) — with refresh.
  4. Device authorization flow — interactive browser login (CLI fallback).
"""
from __future__ import annotations

import base64
import logging
import os
import time
from datetime import datetime, timezone
from typing import cast

import httpx

from feanor.config import Profile, save_config

logger = logging.getLogger(__name__)

_REFRESH_BUFFER_SECONDS = 60


class TokenManager:
    def __init__(self, profile: Profile) -> None:
        self._profile = profile

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_token(self) -> str:
        """Return a valid access token, refreshing transparently if needed."""
        # Strategy 1: static env token
        if static := os.environ.get("FEANOR_TOKEN"):
            if self._is_near_expiry(static):
                logger.warning(
                    "FEANOR_TOKEN is expired or near expiry; "
                    "forwarding anyway — you may get a 401."
                )
            return static

        # Strategy 2: client credentials
        client_id = os.environ.get("FEANOR_CLIENT_ID")
        client_secret = os.environ.get("FEANOR_CLIENT_SECRET")
        if client_id and client_secret:
            return self._client_credentials(client_id, client_secret)

        # Strategy 3: cached token with refresh
        if self._profile.token and not self._is_near_expiry(self._profile.token):
            return self._profile.token

        if self._profile.refresh_token:
            try:
                return self._refresh(self._profile.refresh_token)
            except httpx.HTTPStatusError:
                pass  # fall through to device flow

        # Strategy 4: device authorization flow
        return self._device_flow()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _token_endpoint(self) -> str:
        return (
            f"{self._profile.keycloak_url}"
            f"/realms/{self._profile.realm}"
            f"/protocol/openid-connect/token"
        )

    def _client_credentials(self, client_id: str, client_secret: str) -> str:
        resp = httpx.post(
            self._token_endpoint(),
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return cast(str, resp.json()["access_token"])

    def _refresh(self, refresh_token: str) -> str:
        resp = httpx.post(
            self._token_endpoint(),
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": "feanor-cli",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._cache_tokens(data)
        return cast(str, data["access_token"])

    def _device_flow(self) -> str:
        device_endpoint = (
            f"{self._profile.keycloak_url}"
            f"/realms/{self._profile.realm}"
            f"/protocol/openid-connect/auth/device"
        )
        resp = httpx.post(
            device_endpoint,
            data={"client_id": "feanor-cli"},
            timeout=10,
        )
        resp.raise_for_status()
        device_data = resp.json()

        print(f"\nOpen this URL in your browser:\n  {device_data['verification_uri_complete']}")
        print(f"Or visit {device_data['verification_uri']} and enter code: {device_data['user_code']}\n")

        interval = device_data.get("interval", 5)
        expires_in = device_data.get("expires_in", 300)
        deadline = time.monotonic() + expires_in

        while time.monotonic() < deadline:
            time.sleep(interval)
            token_resp = httpx.post(
                self._token_endpoint(),
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_data["device_code"],
                    "client_id": "feanor-cli",
                },
                timeout=10,
            )
            if token_resp.status_code == 200:
                data = token_resp.json()
                self._cache_tokens(data)
                return cast(str, data["access_token"])

            error = token_resp.json().get("error", "")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval += 5
                continue
            # Any other error (access_denied, expired_token, …) is fatal.
            raise RuntimeError(f"Device flow failed: {error}")

        raise RuntimeError("Device flow timed out — authorization not completed in time.")

    def _cache_tokens(self, data: dict) -> None:
        """Persist access + refresh tokens into the config file."""
        self._profile.token = data["access_token"]
        self._profile.refresh_token = data.get("refresh_token")
        expires_in: int = data.get("expires_in", 900)
        self._profile.token_expires_at = datetime.fromtimestamp(
            time.time() + expires_in, tz=timezone.utc
        )
        save_config(self._profile)

    @staticmethod
    def _is_near_expiry(token: str) -> bool:
        """Return True if the JWT exp claim is within REFRESH_BUFFER_SECONDS."""
        try:
            # JWT is three base64url parts; decode the payload (middle part).
            payload_b64 = token.split(".")[1]
            # Add padding so base64 doesn't complain.
            payload_b64 += "=" * (-len(payload_b64) % 4)
            import json
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            exp: int = payload.get("exp", 0)
            return time.time() + _REFRESH_BUFFER_SECONDS >= exp
        except Exception:
            return False
