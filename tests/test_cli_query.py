"""Unit tests for feanor query CLI command."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from feanor.cli import app
from feanor.exceptions import FeanorQueryError
from feanor.models.query import QueryResult

runner = CliRunner()

_RESULT = QueryResult(
    columns=["id", "value"],
    rows=[{"id": 1, "value": "alpha"}, {"id": 2, "value": "beta"}],
    query_id="q-abc",
    elapsed_ms=42,
)

_EMPTY_RESULT = QueryResult(
    columns=["n"],
    rows=[],
    query_id="q-empty",
    elapsed_ms=10,
)


def _patch_query(result: QueryResult | Exception) -> Any:
    if isinstance(result, Exception):
        mock = AsyncMock(side_effect=result)
    else:
        mock = AsyncMock(return_value=result)
    return patch("feanor.cli.commands.query.AsyncClient") , mock


def _run(args: list[str], query_result: QueryResult | Exception = _RESULT):
    if isinstance(query_result, Exception):
        side_effect = query_result
        async_query = AsyncMock(side_effect=side_effect)
    else:
        async_query = AsyncMock(return_value=query_result)

    mock_client = AsyncMock()
    mock_client.query = async_query
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("feanor.cli.commands.query.AsyncClient", return_value=mock_client):
        return runner.invoke(app, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# table output (default)
# ---------------------------------------------------------------------------


def test_query_table_output_contains_rows() -> None:
    result = _run(["query", "SELECT 1"])
    assert result.exit_code == 0
    assert "alpha" in result.stdout
    assert "beta" in result.stdout


def test_query_table_has_headers() -> None:
    result = _run(["query", "SELECT 1"])
    assert "id" in result.stdout
    assert "value" in result.stdout


def test_query_empty_result_table() -> None:
    result = _run(["query", "SELECT 1"], query_result=_EMPTY_RESULT)
    assert result.exit_code == 0
    assert "0 rows" in result.stdout


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def test_query_json_output() -> None:
    result = _run(["--output", "json", "query", "SELECT 1"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["columns"] == ["id", "value"]
    assert len(parsed["rows"]) == 2
    assert parsed["query_id"] == "q-abc"
    assert "elapsed_ms" in parsed


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------


def test_query_yaml_output() -> None:
    result = _run(["--output", "yaml", "query", "SELECT 1"])
    assert result.exit_code == 0
    parsed = yaml.safe_load(result.stdout)
    assert parsed["columns"] == ["id", "value"]
    assert len(parsed["rows"]) == 2


# ---------------------------------------------------------------------------
# --quiet suppresses footer
# ---------------------------------------------------------------------------


def test_query_quiet_flag() -> None:
    result = _run(["query", "--quiet", "SELECT 1"])
    assert result.exit_code == 0
    # footer goes to stderr; with mix_stderr=False stderr is separate
    assert "q-abc" not in result.stdout


# ---------------------------------------------------------------------------
# FeanorQueryError exits with code 1
# ---------------------------------------------------------------------------


def test_query_error_exits_1() -> None:
    result = _run(["query", "BAD SQL"], query_result=FeanorQueryError("syntax error"))
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# --catalog / --schema are forwarded
# ---------------------------------------------------------------------------


def test_catalog_schema_forwarded() -> None:
    mock_client = AsyncMock()
    mock_client.query = AsyncMock(return_value=_RESULT)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("feanor.cli.commands.query.AsyncClient", return_value=mock_client):
        runner.invoke(
            app,
            ["query", "--catalog", "postgresql", "--schema", "public", "SELECT 1"],
            catch_exceptions=False,
        )

    mock_client.query.assert_awaited_once_with(
        "SELECT 1",
        catalog="postgresql",
        schema="public",
        max_rows=10_000,
    )
