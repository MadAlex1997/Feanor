"""Unit tests for api.app.trino.catalog."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.app.trino.catalog import (
    remove_catalog,
    render_catalog_properties,
    sync_catalog,
)


def _make_connector(
    name: str = "prod-pg",
    conn_type: str = "postgresql",
    config: dict | None = None,
) -> MagicMock:
    now = datetime.now(timezone.utc)
    c = MagicMock()
    c.id = uuid.uuid4()
    c.name = name
    c.type = conn_type
    c.owner = "bob"
    raw = config or {}
    c.config_encrypted = json.dumps(raw).encode()
    c.created_at = now
    c.updated_at = now
    return c


# ---------------------------------------------------------------------------
# render_catalog_properties
# ---------------------------------------------------------------------------


def test_render_postgresql() -> None:
    content = render_catalog_properties(
        "my-pg",
        "postgresql",
        {"host": "db.example.com", "port": 5432, "database": "mydb", "user": "u", "password": "p"},
    )
    assert "connector.name=postgresql" in content
    assert "jdbc:postgresql://db.example.com:5432/mydb" in content
    assert "connection-user=u" in content
    assert "connection-password=p" in content


def test_render_mysql() -> None:
    content = render_catalog_properties(
        "my-mysql",
        "mysql",
        {"host": "mysql.example.com", "port": 3306, "database": "sales", "user": "r", "password": "s"},
    )
    assert "connector.name=mysql" in content
    assert "jdbc:mysql://mysql.example.com:3306/sales" in content


def test_render_s3_minio() -> None:
    content = render_catalog_properties(
        "my-minio",
        "s3",
        {"endpoint": "http://minio:9000", "access_key": "ak", "secret_key": "sk"},
    )
    assert "connector.name=hive" in content
    assert "hive.metastore=file" in content
    assert "hive.s3.endpoint=http://minio:9000" in content
    assert "hive.s3.aws-access-key=ak" in content
    assert "hive.s3.path-style-access=true" in content
    assert "hive.s3.ssl.enabled=false" in content


def test_render_s3_aws_no_endpoint() -> None:
    content = render_catalog_properties("my-s3", "s3", {"access_key": "k", "secret_key": "s"})
    assert "hive.s3.path-style-access=false" in content
    assert "hive.s3.ssl.enabled=true" in content
    assert "hive.s3.endpoint" not in content


def test_render_http() -> None:
    content = render_catalog_properties("my-api", "http", {"base_url": "https://api.example.com"})
    assert "connector.name=http" in content
    assert "https://api.example.com" in content


def test_render_unsupported_type_raises() -> None:
    with pytest.raises(ValueError, match="not supported"):
        render_catalog_properties("x", "kafka", {})


# ---------------------------------------------------------------------------
# sync_catalog — file write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_catalog_writes_file(tmp_path: Path) -> None:
    conn = _make_connector(
        config={"host": "db", "port": 5432, "database": "feanor", "user": "u", "password": "p"},
    )
    with (
        patch("api.app.trino.catalog._CATALOG_DIR", tmp_path),
        patch("api.app.trino.catalog._reload_trino_catalog", new=AsyncMock()),
    ):
        await sync_catalog(conn)

    written = (tmp_path / "prod-pg.properties").read_text()
    assert "connector.name=postgresql" in written


@pytest.mark.asyncio
async def test_sync_catalog_skips_unsupported_type(tmp_path: Path) -> None:
    conn = _make_connector(conn_type="kafka")
    with (
        patch("api.app.trino.catalog._CATALOG_DIR", tmp_path),
        patch("api.app.trino.catalog._reload_trino_catalog", new=AsyncMock()) as mock_reload,
    ):
        await sync_catalog(conn)

    mock_reload.assert_not_called()
    assert not (tmp_path / "prod-pg.properties").exists()


@pytest.mark.asyncio
async def test_sync_catalog_handles_write_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    conn = _make_connector()
    bad_dir = tmp_path / "no-permission"
    bad_dir.mkdir()
    bad_dir.chmod(0o444)

    with (
        patch("api.app.trino.catalog._CATALOG_DIR", bad_dir),
        patch("api.app.trino.catalog._reload_trino_catalog", new=AsyncMock()) as mock_reload,
    ):
        await sync_catalog(conn)

    mock_reload.assert_not_called()

    bad_dir.chmod(0o755)  # restore for cleanup


# ---------------------------------------------------------------------------
# remove_catalog — file deletion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_catalog_deletes_file(tmp_path: Path) -> None:
    conn = _make_connector()
    props_file = tmp_path / "prod-pg.properties"
    props_file.write_text("connector.name=postgresql\n")

    with (
        patch("api.app.trino.catalog._CATALOG_DIR", tmp_path),
        patch("api.app.trino.catalog._reload_trino_catalog", new=AsyncMock()),
    ):
        await remove_catalog(conn)

    assert not props_file.exists()


@pytest.mark.asyncio
async def test_remove_catalog_missing_file_is_noop(tmp_path: Path) -> None:
    conn = _make_connector()
    with (
        patch("api.app.trino.catalog._CATALOG_DIR", tmp_path),
        patch("api.app.trino.catalog._reload_trino_catalog", new=AsyncMock()) as mock_reload,
    ):
        await remove_catalog(conn)

    mock_reload.assert_called_once_with("prod-pg")
