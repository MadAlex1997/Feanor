"""DuckDB session wrapper for use inside Fëanor execution workers.

Usage::

    from feanor.worker.duckdb import DuckDBSession

    with DuckDBSession() as db:
        rows = db.query("SELECT * FROM read_parquet('s3://bucket/file.parquet')")
        db.execute("COPY (SELECT ...) TO 's3://out/result.parquet' (FORMAT PARQUET)")
"""
from __future__ import annotations

import os
from types import TracebackType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import duckdb as _duckdb

_DEFAULT_MEMORY_LIMIT = "1GB"


class DuckDBSession:
    """Context manager wrapping a DuckDB in-memory connection.

    Automatically configures S3/MinIO access from environment or constructor args.
    """

    def __init__(
        self,
        *,
        s3_endpoint: str | None = None,
        s3_access_key: str | None = None,
        s3_secret_key: str | None = None,
        read_only: bool = False,
        memory_limit: str = _DEFAULT_MEMORY_LIMIT,
    ) -> None:
        self._s3_endpoint = s3_endpoint or os.environ.get("FEANOR_S3_ENDPOINT")
        self._s3_access_key = s3_access_key or os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("MINIO_ROOT_USER")
        self._s3_secret_key = s3_secret_key or os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("MINIO_ROOT_PASSWORD")
        self._read_only = read_only
        self._memory_limit = memory_limit
        self._conn: "_duckdb.DuckDBPyConnection | None" = None

    def __enter__(self) -> "DuckDBSession":
        import duckdb

        self._conn = duckdb.connect(database=":memory:", read_only=self._read_only)
        self._conn.execute(f"SET memory_limit='{self._memory_limit}'")

        # Enable S3/MinIO access.
        self._conn.execute("INSTALL httpfs")
        self._conn.execute("LOAD httpfs")

        if self._s3_access_key:
            self._conn.execute(f"SET s3_access_key_id='{self._s3_access_key}'")
        if self._s3_secret_key:
            self._conn.execute(f"SET s3_secret_access_key='{self._s3_secret_key}'")

        if self._s3_endpoint:
            # MinIO or custom S3-compatible endpoint.
            self._conn.execute(f"SET s3_endpoint='{_strip_scheme(self._s3_endpoint)}'")
            self._conn.execute("SET s3_url_style='path'")
            self._conn.execute("SET s3_use_ssl=false")
            self._conn.execute("SET s3_region='us-east-1'")
        else:
            # Standard AWS S3.
            self._conn.execute("SET s3_url_style='vhost'")

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute *sql* and return all rows as a list of dicts."""
        if self._conn is None:
            raise RuntimeError("DuckDBSession is not open; use as a context manager")
        rel = self._conn.execute(sql)
        columns = [desc[0] for desc in rel.description]
        return [dict(zip(columns, row)) for row in rel.fetchall()]

    def query_df(self, sql: str) -> Any:
        """Execute *sql* and return a pandas DataFrame.

        Raises ImportError if pandas is not installed in the worker environment.
        """
        try:
            import pandas  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "pandas is required for query_df(); install it in your worker image: "
                "pip install pandas"
            ) from exc

        if self._conn is None:
            raise RuntimeError("DuckDBSession is not open; use as a context manager")
        return self._conn.execute(sql).df()

    def execute(self, sql: str) -> None:
        """Execute *sql* without returning results (for COPY, CREATE, INSERT, etc.)."""
        if self._conn is None:
            raise RuntimeError("DuckDBSession is not open; use as a context manager")
        self._conn.execute(sql)


def _strip_scheme(endpoint: str) -> str:
    """Remove http:// or https:// prefix for DuckDB s3_endpoint setting."""
    for prefix in ("https://", "http://"):
        if endpoint.startswith(prefix):
            return endpoint[len(prefix):]
    return endpoint
