"""Scenario B: DuckDB worker utility — read Parquet from MinIO.

This test exercises the DuckDBSession utility against a live MinIO instance.
It does NOT go through the full execution dispatch pipeline (that would require
a built worker image). Instead it exercises the SDK utility directly.

Requires: full Docker Compose stack (`pytest -m e2e`).
"""
from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.e2e

duckdb = pytest.importorskip("duckdb", reason="duckdb not installed")

_SAMPLE_KEY = "test-data/sample.parquet"
_TEST_BUCKET = "feanor-test"
_MINIO_URL = "http://localhost:9000"
_MINIO_ACCESS = "minioadmin"
_MINIO_SECRET = "changeme"


def test_duckdb_session_reads_parquet_from_minio(setup_test_bucket) -> None:
    """DuckDBSession can query a Parquet file hosted on MinIO."""
    from feanor.worker.duckdb import DuckDBSession

    s3_path = f"s3://{_TEST_BUCKET}/{_SAMPLE_KEY}"

    with DuckDBSession(
        s3_endpoint=_MINIO_URL,
        s3_access_key=_MINIO_ACCESS,
        s3_secret_key=_MINIO_SECRET,
    ) as db:
        rows = db.query(f"SELECT * FROM read_parquet('{s3_path}') ORDER BY id")

    assert len(rows) == 10
    assert rows[0]["id"] == 1
    assert rows[9]["id"] == 10
    col_names = set(rows[0].keys())
    assert "id" in col_names
    assert "name" in col_names
    assert "value" in col_names


def test_duckdb_session_count_from_minio(setup_test_bucket) -> None:
    """COUNT(*) via DuckDBSession returns 10 rows."""
    from feanor.worker.duckdb import DuckDBSession

    s3_path = f"s3://{_TEST_BUCKET}/{_SAMPLE_KEY}"

    with DuckDBSession(
        s3_endpoint=_MINIO_URL,
        s3_access_key=_MINIO_ACCESS,
        s3_secret_key=_MINIO_SECRET,
    ) as db:
        result = db.query(f"SELECT COUNT(*) AS n FROM read_parquet('{s3_path}')")

    assert result[0]["n"] == 10


def test_duckdb_write_result_to_minio(setup_test_bucket, minio_client) -> None:
    """write_result() uploads a Parquet file to MinIO successfully."""
    import uuid

    from feanor.worker.result import write_result

    dest_key = f"test-results/{uuid.uuid4().hex}.parquet"
    dest_ref = f"s3://{_TEST_BUCKET}/{dest_key}"

    rows = [{"x": i, "y": str(i)} for i in range(5)]

    write_result(rows, result_ref=dest_ref)

    # Verify it can be read back.
    with DuckDBSession(
        s3_endpoint=_MINIO_URL,
        s3_access_key=_MINIO_ACCESS,
        s3_secret_key=_MINIO_SECRET,
    ) as db:
        back = db.query(f"SELECT COUNT(*) AS n FROM read_parquet('{dest_ref}')")

    assert back[0]["n"] == 5

    # Cleanup.
    minio_client.delete_object(Bucket=_TEST_BUCKET, Key=dest_key)
