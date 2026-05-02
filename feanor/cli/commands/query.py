"""feanor query — run federated SQL via Trino."""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.table import Column, Table

from feanor.async_client import AsyncClient
from feanor.cli.output import err_console
from feanor.exceptions import FeanorQueryError
from feanor.models.query import QueryResult

_stdout = Console(highlight=False)


def _ctx_opts(ctx: typer.Context) -> tuple[Optional[str], str, bool]:
    obj = ctx.obj or {}
    return obj.get("profile"), obj.get("output", "table"), obj.get("quiet", False)


def run_query(
    ctx: typer.Context,
    sql: str = typer.Argument(..., help="SQL statement to execute against Trino."),
    catalog: Optional[str] = typer.Option(None, "--catalog", "-c", help="Default Trino catalog."),
    schema: Optional[str] = typer.Option(None, "--schema", "-s", help="Default Trino schema."),
    max_rows: int = typer.Option(10_000, "--max-rows", help="Abort if result exceeds this many rows."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress footer (row count / query id)."),
) -> None:
    """Execute a SQL query against Trino and print the results."""
    profile, output_fmt, ctx_quiet = _ctx_opts(ctx)
    quiet = quiet or ctx_quiet

    result: Optional[QueryResult] = None

    async def _run() -> None:
        nonlocal result
        async with AsyncClient(profile) as client:
            result = await client.query(sql, catalog=catalog, schema=schema, max_rows=max_rows)

    try:
        asyncio.run(_run())
    except FeanorQueryError as exc:
        err_console.print(f"[red]query error:[/red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)

    assert result is not None
    _render(result, output_fmt, quiet)


def _render(result: QueryResult, output_fmt: str, quiet: bool) -> None:
    if output_fmt == "json":
        sys.stdout.write(
            json.dumps(
                {
                    "columns": result.columns,
                    "rows": result.rows,
                    "query_id": result.query_id,
                    "elapsed_ms": result.elapsed_ms,
                },
                default=str,
            )
        )
        sys.stdout.write("\n")
        return

    if output_fmt == "yaml":
        sys.stdout.write(
            yaml.safe_dump(
                {
                    "columns": result.columns,
                    "rows": result.rows,
                    "query_id": result.query_id,
                    "elapsed_ms": result.elapsed_ms,
                },
                default_flow_style=False,
            )
        )
        return

    # table (default)
    if not result.rows:
        _stdout.print("[dim]0 rows returned.[/dim]")
        if not quiet:
            err_console.print(
                f"[dim]0 rows · {result.elapsed_ms}ms · query_id: {result.query_id}[/dim]"
            )
        return

    cols = [
        Column(c, justify="right" if _looks_numeric(result.rows, c) else "left")
        for c in result.columns
    ]
    table = Table(*cols, show_header=True, header_style="bold")
    for row in result.rows:
        table.add_row(*[str(row.get(c, "")) for c in result.columns])
    _stdout.print(table)

    if not quiet:
        err_console.print(
            f"[dim]{len(result.rows)} row(s) · {result.elapsed_ms}ms"
            f" · query_id: {result.query_id}[/dim]"
        )


def _looks_numeric(rows: list[dict], col: str) -> bool:
    for row in rows[:5]:
        val = row.get(col)
        if val is not None and not isinstance(val, (int, float)):
            return False
    return True
