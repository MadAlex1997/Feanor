"""Profile loading from ~/.feanor/config.yaml and environment overrides.

Resolution order (highest to lowest priority):
  --profile flag > FEANOR_PROFILE env > default_profile in YAML > "local" hardcoded

FEANOR_API_URL overrides only api_url; all other fields come from the YAML.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

_CONFIG_PATH = Path.home() / ".feanor" / "config.yaml"

_DEFAULT_LOCAL = {
    "api_url": "http://localhost:8000",
    "keycloak_url": "http://localhost:8080",
    "realm": "feanor",
}


class Profile(BaseModel):
    name: str
    api_url: str
    keycloak_url: str
    realm: str
    token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None


def load_config(profile: str | None = None) -> Profile:
    """Load and return the active Profile.

    Args:
        profile: Override the profile name. Takes precedence over FEANOR_PROFILE
                 and the default_profile key in the config file.

    Raises:
        ValueError: If the requested profile does not exist in the config file.
    """
    raw = _read_yaml()

    profile_name = (
        profile
        or os.environ.get("FEANOR_PROFILE")
        or raw.get("default_profile", "local")
    )

    profiles: dict = raw.get("profiles", {})

    if profile_name not in profiles:
        if profile_name == "local" and not profiles:
            data = {"name": "local", **_DEFAULT_LOCAL}
        else:
            available = ", ".join(profiles) or "(none)"
            raise ValueError(
                f"Profile {profile_name!r} not found in {_CONFIG_PATH}. "
                f"Available profiles: {available}"
            )
    else:
        entry = profiles[profile_name]
        data = {"name": profile_name, **entry}

    # FEANOR_API_URL overrides only api_url.
    if api_url := os.environ.get("FEANOR_API_URL"):
        data["api_url"] = api_url

    return Profile(**data)


def save_config(profile: Profile) -> None:
    """Persist token fields back into the config file for the given profile."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = _read_yaml()
    profiles: dict = raw.setdefault("profiles", {})
    existing = profiles.setdefault(profile.name, {})

    existing.update(
        {
            k: v
            for k, v in {
                "api_url": profile.api_url,
                "keycloak_url": profile.keycloak_url,
                "realm": profile.realm,
                "token": profile.token,
                "refresh_token": profile.refresh_token,
                "token_expires_at": (
                    profile.token_expires_at.isoformat()
                    if profile.token_expires_at
                    else None
                ),
            }.items()
            if v is not None
        }
    )

    if "default_profile" not in raw:
        raw["default_profile"] = profile.name

    with _CONFIG_PATH.open("w") as fh:
        yaml.safe_dump(raw, fh, default_flow_style=False)


def _read_yaml() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open() as fh:
        return yaml.safe_load(fh) or {}
