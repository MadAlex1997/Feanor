"""Register the Fëanor default Airflow connection.

Run once by airflow-init on every fresh stack startup. Idempotent — updates
the connection if it already exists rather than raising an error.
"""
from __future__ import annotations

import json
import os

from airflow.models import Connection
from airflow.utils import db as airflow_db

api_url = os.environ.get("FEANOR_API_URL", "http://api:8080")
client_id = os.environ.get("FEANOR_CLIENT_ID", "airflow-sa")
client_secret = os.environ.get("FEANOR_CLIENT_SECRET", "")
keycloak_url = os.environ.get("FEANOR_KEYCLOAK_URL", "http://keycloak:8080")
realm = os.environ.get("FEANOR_REALM", "feanor")

conn = Connection(
    conn_id="feanor_default",
    conn_type="generic",
    host=api_url,
    login=client_id,
    password=client_secret,
    extra=json.dumps({"keycloak_url": keycloak_url, "realm": realm}),
)

with airflow_db.create_session() as session:
    existing = session.query(Connection).filter_by(conn_id="feanor_default").first()
    if existing:
        existing.host = conn.host
        existing.login = conn.login
        existing.set_password(client_secret)
        existing.extra = conn.extra
        print("Updated existing connection: feanor_default")
    else:
        session.add(conn)
        print("Created connection: feanor_default")
    session.commit()
