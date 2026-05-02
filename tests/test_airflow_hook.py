"""Unit tests for FeanorHook.

These tests mock out Airflow internals so they run without a live Airflow
database or Docker stack.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("airflow.hooks.base", reason="apache-airflow>=2.x not installed")


@pytest.fixture()
def mock_connection():
    conn = MagicMock()
    conn.host = "http://api:8080"
    conn.login = "airflow-sa"
    conn.password = "secret123"
    conn.extra = json.dumps({"keycloak_url": "http://keycloak:8080", "realm": "feanor"})
    conn.extra_dejson = {"keycloak_url": "http://keycloak:8080", "realm": "feanor"}
    return conn


def test_get_client_sets_env_vars(mock_connection, monkeypatch):
    """get_client() should inject connection details into env vars."""
    with (
        patch(
            "airflow.hooks.base.BaseHook.get_connection",
            return_value=mock_connection,
        ),
        patch("feanor.client.Client.__init__", return_value=None) as mock_client_init,
    ):
        from dags.hooks.feanor_hook import FeanorHook

        hook = FeanorHook(conn_id="feanor_default")
        hook.get_client()

        import os

        assert os.environ["FEANOR_API_URL"] == "http://api:8080"
        assert os.environ["FEANOR_CLIENT_ID"] == "airflow-sa"
        assert os.environ["FEANOR_CLIENT_SECRET"] == "secret123"
        assert os.environ["FEANOR_KEYCLOAK_URL"] == "http://keycloak:8080"
        assert os.environ["FEANOR_REALM"] == "feanor"
        mock_client_init.assert_called_once()


def test_get_client_falls_back_to_env_vars(monkeypatch):
    """When connection fields are absent, get_client() falls back to env vars."""
    conn = MagicMock()
    conn.host = ""
    conn.login = ""
    conn.password = ""
    conn.extra = ""
    conn.extra_dejson = {}

    monkeypatch.setenv("FEANOR_API_URL", "http://fallback-api:8080")
    monkeypatch.setenv("FEANOR_CLIENT_ID", "fallback-client")
    monkeypatch.setenv("FEANOR_CLIENT_SECRET", "fallback-secret")
    monkeypatch.setenv("FEANOR_KEYCLOAK_URL", "http://fallback-kc:8080")
    monkeypatch.setenv("FEANOR_REALM", "fallback-realm")

    with (
        patch(
            "airflow.hooks.base.BaseHook.get_connection",
            return_value=conn,
        ),
        patch("feanor.client.Client.__init__", return_value=None),
    ):
        from dags.hooks.feanor_hook import FeanorHook

        hook = FeanorHook()
        hook.get_client()

        import os

        assert os.environ["FEANOR_API_URL"] == "http://fallback-api:8080"
        assert os.environ["FEANOR_CLIENT_ID"] == "fallback-client"


def test_default_conn_id():
    """FeanorHook uses feanor_default as the default connection ID."""
    from dags.hooks.feanor_hook import FeanorHook

    hook = FeanorHook()
    assert hook.conn_id == "feanor_default"


def test_custom_conn_id():
    from dags.hooks.feanor_hook import FeanorHook

    hook = FeanorHook(conn_id="feanor_staging")
    assert hook.conn_id == "feanor_staging"
