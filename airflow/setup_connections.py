"""Register the Fëanor default Airflow connection.

Run once by airflow-init on every fresh stack startup. Idempotent — deletes
and recreates the connection so settings are always up to date.
"""
from __future__ import annotations

import json
import os
import subprocess

api_url = os.environ.get("FEANOR_API_URL", "http://api:8080")
client_id = os.environ.get("FEANOR_CLIENT_ID", "airflow-sa")
client_secret = os.environ.get("FEANOR_CLIENT_SECRET", "")
keycloak_url = os.environ.get("FEANOR_KEYCLOAK_URL", "http://keycloak:8080")
realm = os.environ.get("FEANOR_REALM", "feanor")

conn_json = json.dumps({
    "conn_type": "generic",
    "host": api_url,
    "login": client_id,
    "password": client_secret,
    "extra": json.dumps({"keycloak_url": keycloak_url, "realm": realm}),
})

subprocess.run(["airflow", "connections", "delete", "feanor_default"], capture_output=True)
subprocess.run(
    ["airflow", "connections", "add", "feanor_default", "--conn-json", conn_json],
    check=True,
)
print("Registered connection: feanor_default")
