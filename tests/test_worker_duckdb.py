"""Unit tests for feanor.worker.duckdb.DuckDBSession."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

# Skip all tests in this module if duckdb is not installed.
duckdb = pytest.importorskip("duckdb", reason="duckdb not installed in this environment")

from feanor.worker.duckdb import DuckDBSession, _strip_scheme


# ---------------------------------------------------------------------------
# _strip_scheme helper
# ---------------------------------------------------------------------------


def test_strip_scheme_http() -> None:
    assert _strip_scheme("http://minio:9000") == "minio:9000"


def test_strip_scheme_https() -> None:
    assert _strip_scheme("https://s3.amazonaws.com") == "s3.amazonaws.com"


def test_strip_scheme_no_scheme() -> None:
    assert _strip_scheme("minio:9000") == "minio:9000"


# ---------------------------------------------------------------------------
# DuckDBSession — basic query
# ---------------------------------------------------------------------------


def test_session_simple_query() -> None:
    with DuckDBSession() as db:
        rows = db.query("SELECT 42 AS n, 'hello' AS s")
    assert rows == [{"n": 42, "s": "hello"}]


def test_session_execute_no_return() -> None:
    with DuckDBSession() as db:
        db.execute("CREATE TABLE t (x INTEGER)")
        db.execute("INSERT INTO t VALUES (1), (2)")
        rows = db.query("SELECT x FROM t ORDER BY x")
    assert rows == [{"x": 1}, {"x": 2}]


def test_session_closes_on_exit() -> None:
    session = DuckDBSession()
    with session:
        assert session._conn is not None
    assert session._conn is None


def test_session_closes_on_exception() -> None:
    session = DuckDBSession()
    try:
        with session:
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert session._conn is None


def test_session_outside_context_raises() -> None:
    session = DuckDBSession()
    with pytest.raises(RuntimeError, match="context manager"):
        session.query("SELECT 1")


# ---------------------------------------------------------------------------
# S3 / MinIO configuration — verify SET statements via session.execute spy
# ---------------------------------------------------------------------------


def test_s3_endpoint_sets_path_style(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEANOR_S3_ENDPOINT", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_ROOT_USER", raising=False)
    monkeypatch.delenv("MINIO_ROOT_PASSWORD", raising=False)

    executed: list[str] = []
    session = DuckDBSession(
        s3_endpoint="http://minio:9000",
        s3_access_key="ak",
        s3_secret_key="sk",
    )

    original_enter = DuckDBSession.__enter__

    def _spying_enter(self):
        result = original_enter(self)
        # Wrap execute to capture subsequent calls; re-point _conn.execute via session
        original_execute = self.execute

        def _spy(sql: str) -> None:
            executed.append(sql)
            original_execute(sql)

        self.execute = _spy  # type: ignore[method-assign]
        return result

    # Re-run __enter__ with spy in place.
    # Simpler: capture by inspecting the session's _s3_* attributes.
    assert session._s3_endpoint == "http://minio:9000"
    assert session._s3_access_key == "ak"
    assert session._s3_secret_key == "sk"

    # Verify path-style logic: endpoint present → path style.
    with DuckDBSession(s3_endpoint="http://minio:9000", s3_access_key="ak", s3_secret_key="sk") as db:
        # SET s3_url_style should have applied — confirm by reading the setting.
        rows = db.query("SELECT current_setting('s3_url_style') AS v")
        assert rows[0]["v"] == "path"


def test_no_endpoint_sets_vhost_style(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEANOR_S3_ENDPOINT", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_ROOT_USER", raising=False)
    monkeypatch.delenv("MINIO_ROOT_PASSWORD", raising=False)

    with DuckDBSession() as db:
        rows = db.query("SELECT current_setting('s3_url_style') AS v")
        assert rows[0]["v"] == "vhost"
