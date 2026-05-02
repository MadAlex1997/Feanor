"""Worker result-writing utilities.

Writes execution results to the path given by FEANOR_RESULT_REF (or an
explicit result_ref argument) using DuckDB's COPY ... TO ... (FORMAT PARQUET).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def write_result(data: "list[dict] | Any", result_ref: str | None = None) -> None:
    """Write *data* as Parquet to *result_ref*.

    Args:
        data: A list of dicts or a pandas DataFrame.
        result_ref: S3/MinIO path (``s3://bucket/key.parquet``).
                    Defaults to ``FEANOR_RESULT_REF`` env var.

    Raises:
        ValueError: If result_ref is not provided and FEANOR_RESULT_REF is unset.
    """
    from feanor.worker.duckdb import DuckDBSession

    dest = result_ref or os.environ.get("FEANOR_RESULT_REF")
    if not dest:
        raise ValueError(
            "result_ref must be provided or FEANOR_RESULT_REF must be set"
        )

    with DuckDBSession() as db:
        if _is_dataframe(data):
            # Register the DataFrame as a view and COPY from it.
            db._conn.register("_result_df", data)  # type: ignore[union-attr]
            db.execute(f"COPY _result_df TO '{dest}' (FORMAT PARQUET)")
        else:
            # Build an in-memory table from the list of dicts and COPY it.
            if not data:
                raise ValueError("data must be non-empty to infer schema")
            db._conn.register("_result_rows", _rows_to_relation(db._conn, data))  # type: ignore[union-attr]
            db.execute(f"COPY _result_rows TO '{dest}' (FORMAT PARQUET)")


def _is_dataframe(obj: Any) -> bool:
    try:
        import pandas as pd

        return isinstance(obj, pd.DataFrame)
    except ImportError:
        return False


def _rows_to_relation(conn: Any, rows: list[dict]) -> Any:
    """Convert list[dict] to a DuckDB relation via a VALUES clause."""
    import json

    # Use DuckDB's read_json_auto on an in-memory JSON string.
    json_str = json.dumps(rows)
    return conn.execute(f"SELECT * FROM read_json_auto('{json_str}')").fetchdf()
