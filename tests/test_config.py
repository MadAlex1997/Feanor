"""Unit tests for feanor.config — profile loading and env overrides."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from feanor.config import Profile, load_config, _DEFAULT_LOCAL


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        yaml.safe_dump(data, fh)


def test_missing_config_file_returns_local_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("FEANOR_PROFILE", raising=False)
    monkeypatch.delenv("FEANOR_API_URL", raising=False)

    # Patch _CONFIG_PATH to point at the tmp home
    cfg_path = tmp_path / ".feanor" / "config.yaml"
    with patch("feanor.config._CONFIG_PATH", cfg_path):
        profile = load_config()

    assert profile.name == "local"
    assert profile.api_url == _DEFAULT_LOCAL["api_url"]
    assert profile.keycloak_url == _DEFAULT_LOCAL["keycloak_url"]


def test_explicit_profile_arg_wins(tmp_path, monkeypatch):
    monkeypatch.delenv("FEANOR_PROFILE", raising=False)
    monkeypatch.delenv("FEANOR_API_URL", raising=False)
    cfg_path = tmp_path / ".feanor" / "config.yaml"
    _write_yaml(cfg_path, {
        "default_profile": "local",
        "profiles": {
            "local": {**_DEFAULT_LOCAL},
            "staging": {"api_url": "https://api.staging.example.com", "keycloak_url": "https://auth.staging.example.com", "realm": "feanor"},
        },
    })
    with patch("feanor.config._CONFIG_PATH", cfg_path):
        profile = load_config(profile="staging")

    assert profile.name == "staging"
    assert "staging" in profile.api_url


def test_feanor_profile_env_overrides_yaml_default(tmp_path, monkeypatch):
    monkeypatch.setenv("FEANOR_PROFILE", "staging")
    monkeypatch.delenv("FEANOR_API_URL", raising=False)
    cfg_path = tmp_path / ".feanor" / "config.yaml"
    _write_yaml(cfg_path, {
        "default_profile": "local",
        "profiles": {
            "local": {**_DEFAULT_LOCAL},
            "staging": {"api_url": "https://api.staging.example.com", "keycloak_url": "https://auth.staging.example.com", "realm": "feanor"},
        },
    })
    with patch("feanor.config._CONFIG_PATH", cfg_path):
        profile = load_config()

    assert profile.name == "staging"


def test_feanor_api_url_overrides_api_url_only(tmp_path, monkeypatch):
    monkeypatch.delenv("FEANOR_PROFILE", raising=False)
    monkeypatch.setenv("FEANOR_API_URL", "http://override:9999")
    cfg_path = tmp_path / ".feanor" / "config.yaml"
    _write_yaml(cfg_path, {
        "default_profile": "local",
        "profiles": {"local": {**_DEFAULT_LOCAL}},
    })
    with patch("feanor.config._CONFIG_PATH", cfg_path):
        profile = load_config()

    assert profile.api_url == "http://override:9999"
    assert profile.keycloak_url == _DEFAULT_LOCAL["keycloak_url"]


def test_unknown_profile_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.delenv("FEANOR_PROFILE", raising=False)
    monkeypatch.delenv("FEANOR_API_URL", raising=False)
    cfg_path = tmp_path / ".feanor" / "config.yaml"
    _write_yaml(cfg_path, {
        "default_profile": "local",
        "profiles": {"local": {**_DEFAULT_LOCAL}},
    })
    with patch("feanor.config._CONFIG_PATH", cfg_path):
        with pytest.raises(ValueError, match="nonexistent"):
            load_config(profile="nonexistent")


def test_profile_is_pydantic_model(tmp_path, monkeypatch):
    monkeypatch.delenv("FEANOR_PROFILE", raising=False)
    monkeypatch.delenv("FEANOR_API_URL", raising=False)
    cfg_path = tmp_path / ".feanor" / "config.yaml"
    with patch("feanor.config._CONFIG_PATH", cfg_path):
        profile = load_config()
    assert isinstance(profile, Profile)
