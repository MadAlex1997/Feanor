from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

import typer

from feanor.async_client import AsyncClient
from feanor.cli.output import error, render
from feanor.exceptions import FeanorAPIError

app = typer.Typer(help="Manage datasets.")

_COLS = ["id", "name", "source_ref", "created_by", "created_at"]


def _ctx_opts(ctx: typer.Context) -> tuple[Optional[str], str, bool]:
    obj = ctx.obj or {}
    return obj.get("profile"), obj.get("output", "table"), obj.get("quiet", False)


@app.command("list")
def list_datasets(
    ctx: typer.Context,
    created_by: Optional[str] = typer.Option(None, "--created-by"),
) -> None:
    """List registered datasets."""
    profile, output_fmt, quiet = _ctx_opts(ctx)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            filters = {}
            if created_by:
                filters["created_by"] = created_by
            results = await client.datasets.list(**filters)
        render(results, output_fmt, quiet, columns=_COLS)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def get(ctx: typer.Context, dataset_id: str = typer.Argument(...)) -> None:
    """Show details for a dataset."""
    profile, output_fmt, quiet = _ctx_opts(ctx)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            result = await client.datasets.get(dataset_id)
        render(result, output_fmt, quiet)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def register(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    source: str = typer.Option(..., "--source"),
    schema_hints: Optional[str] = typer.Option(None, "--schema-hints", help="JSON string"),
) -> None:
    """Register a new dataset."""
    profile, output_fmt, quiet = _ctx_opts(ctx)
    hints = None
    if schema_hints:
        try:
            hints = json.loads(schema_hints)
        except json.JSONDecodeError as exc:
            error(f"invalid --schema-hints JSON: {exc}")
            raise typer.Exit(1)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            result = await client.datasets.register(name=name, source=source, schema_hints=hints)
        render(result, output_fmt, quiet)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def delete(ctx: typer.Context, dataset_id: str = typer.Argument(...)) -> None:
    """Delete a dataset registration."""
    profile, output_fmt, quiet = _ctx_opts(ctx)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            await client.datasets.delete(dataset_id)
        if not quiet:
            typer.echo(f"Deleted dataset {dataset_id}")

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)
