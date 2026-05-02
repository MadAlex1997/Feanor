"""Trino catalog file management.

Writes/removes .properties files in TRINO_CATALOG_DIR and attempts a
hot-reload via the Trino management API. Catalog sync failures are logged
but never propagate — the connector DB record is the source of truth.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from api.app.models.connector import Connector

logger = logging.getLogger(__name__)

_CATALOG_DIR = Path(os.environ.get("TRINO_CATALOG_DIR", "/etc/trino/catalog"))
_TRINO_HOST = os.environ.get("TRINO_HOST", "trino")
_TRINO_PORT = os.environ.get("TRINO_PORT", "8080")

_SUPPORTED_TYPES = {"postgresql", "mysql", "s3", "http"}


def render_catalog_properties(name: str, connector_type: str, config: dict[str, Any]) -> str:
    """Return .properties file content for a connector.

    Raises ValueError for unsupported connector types.
    """
    if connector_type not in _SUPPORTED_TYPES:
        raise ValueError(
            f"connector type {connector_type!r} is not supported for Trino catalog generation; "
            f"supported types: {sorted(_SUPPORTED_TYPES)}"
        )

    if connector_type == "postgresql":
        host = config.get("host", "postgres")
        port = config.get("port", 5432)
        database = config.get("database", "feanor")
        user = config.get("user", "")
        password = config.get("password", "")
        return (
            f"connector.name=postgresql\n"
            f"connection-url=jdbc:postgresql://{host}:{port}/{database}\n"
            f"connection-user={user}\n"
            f"connection-password={password}\n"
        )

    if connector_type == "mysql":
        host = config.get("host", "")
        port = config.get("port", 3306)
        database = config.get("database", "")
        user = config.get("user", "")
        password = config.get("password", "")
        return (
            f"connector.name=mysql\n"
            f"connection-url=jdbc:mysql://{host}:{port}/{database}\n"
            f"connection-user={user}\n"
            f"connection-password={password}\n"
        )

    if connector_type == "s3":
        endpoint = config.get("endpoint", "")
        access_key = config.get("access_key", "")
        secret_key = config.get("secret_key", "")
        catalog_dir = config.get("catalog_dir", f"/data/trino-hive-catalog/{name}")
        # Use path-style for MinIO (custom endpoint); vhost only for AWS.
        path_style = "true" if endpoint else "false"
        ssl = "false" if endpoint else "true"
        lines = [
            "connector.name=hive",
            "hive.metastore=file",
            f"hive.metastore.catalog.dir={catalog_dir}",
            "hive.non-managed-table-writes-enabled=true",
        ]
        if endpoint:
            lines.append(f"hive.s3.endpoint={endpoint}")
        if access_key:
            lines.append(f"hive.s3.aws-access-key={access_key}")
        if secret_key:
            lines.append(f"hive.s3.aws-secret-key={secret_key}")
        lines.append(f"hive.s3.path-style-access={path_style}")
        lines.append(f"hive.s3.ssl.enabled={ssl}")
        return "\n".join(lines) + "\n"

    # http connector
    base_url = config.get("base_url", "")
    return (
        f"connector.name=http\n"
        f"http.base-url={base_url}\n"
    )


def _catalog_path(connector_name: str) -> Path:
    return _CATALOG_DIR / f"{connector_name}.properties"


def _decode_config(raw: bytes | None) -> dict[str, Any]:
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


async def _reload_trino_catalog(catalog_name: str) -> None:
    """Best-effort Trino catalog reload — logs on failure, never raises."""
    url = f"http://{_TRINO_HOST}:{_TRINO_PORT}/v1/catalog/{catalog_name}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url)
            if resp.status_code not in (200, 201, 204):
                logger.warning(
                    "Trino catalog reload returned %d for %r — "
                    "a manual Trino restart may be required",
                    resp.status_code,
                    catalog_name,
                )
    except Exception as exc:
        logger.warning(
            "Could not reach Trino to reload catalog %r (%s); "
            "connector registered but Trino restart may be required",
            catalog_name,
            exc,
        )


async def sync_catalog(connector: Connector) -> None:
    """Write (or overwrite) the Trino catalog file for *connector*.

    Called after POST and PATCH /v1/connectors. Logs and returns on error.
    """
    config = _decode_config(connector.config_encrypted)
    try:
        content = render_catalog_properties(connector.name, connector.type, config)
    except ValueError as exc:
        logger.info("Skipping Trino catalog sync for connector %r: %s", connector.name, exc)
        return

    path = _catalog_path(connector.name)
    try:
        _CATALOG_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info("Wrote Trino catalog file: %s", path)
    except OSError as exc:
        logger.error("Failed to write Trino catalog file %s: %s", path, exc)
        return

    await _reload_trino_catalog(connector.name)


async def remove_catalog(connector: Connector) -> None:
    """Delete the Trino catalog file for *connector*.

    Called after DELETE /v1/connectors/{id}. Logs and returns on error.
    """
    path = _catalog_path(connector.name)
    try:
        path.unlink(missing_ok=True)
        logger.info("Removed Trino catalog file: %s", path)
    except OSError as exc:
        logger.error("Failed to remove Trino catalog file %s: %s", path, exc)
        return

    await _reload_trino_catalog(connector.name)
