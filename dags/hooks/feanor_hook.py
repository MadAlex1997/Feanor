"""Airflow hook that wraps the feanor SDK.

DAG authors choose one of two patterns:

  # Simple: sync helper (env vars only, no Airflow Connection needed)
  FeanorHook().inject_env()
  asyncio.run(my_async_fn())   # uses AsyncClient() inside

  # Full: reads credentials from the Airflow Connection store
  hook = FeanorHook(conn_id="feanor_default")
  hook.inject_env()   # equivalent to calling get_client() for side effects

Connection fields (conn_type=generic):
  host:     Fëanor API URL  (e.g. http://api:8080)
  login:    client_id
  password: client_secret
  extra:    JSON {"keycloak_url": "...", "realm": "..."}
"""
from __future__ import annotations

import os

from airflow.hooks.base import BaseHook


class FeanorHook(BaseHook):
    conn_type = "feanor"
    hook_name = "Fëanor"

    def __init__(self, conn_id: str = "feanor_default") -> None:
        super().__init__()
        self.conn_id = conn_id

    # ------------------------------------------------------------------
    # Primary interface
    # ------------------------------------------------------------------

    def inject_env(self) -> None:
        """Resolve connection details and inject them as environment variables.

        Reads from the Airflow Connection store for the given conn_id, falling
        back to env vars already set for each missing field. After this call,
        the SDK's TokenManager and load_config() will pick up the correct
        credentials without further configuration.
        """
        conn = self.get_connection(self.conn_id)
        extra: dict = conn.extra_dejson if conn.extra else {}

        os.environ["FEANOR_API_URL"] = (
            conn.host or os.environ.get("FEANOR_API_URL", "http://localhost:8000")
        )
        os.environ["FEANOR_CLIENT_ID"] = (
            conn.login or os.environ.get("FEANOR_CLIENT_ID", "")
        )
        os.environ["FEANOR_CLIENT_SECRET"] = (
            conn.password or os.environ.get("FEANOR_CLIENT_SECRET", "")
        )
        os.environ["FEANOR_KEYCLOAK_URL"] = (
            extra.get("keycloak_url")
            or os.environ.get("FEANOR_KEYCLOAK_URL", "http://localhost:8080")
        )
        os.environ["FEANOR_REALM"] = (
            extra.get("realm") or os.environ.get("FEANOR_REALM", "feanor")
        )

    def get_client(self):
        """Inject env and return a sync-compatible Client reference.

        Note: SDK resource methods (submit, query, etc.) are async. Use
        inject_env() + asyncio.run() with AsyncClient for actual API calls.
        get_client() is provided for compatibility and testing.
        """
        self.inject_env()
        from feanor.client import Client

        return Client()
