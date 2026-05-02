from __future__ import annotations

import asyncio
import sys
from typing import Optional

import typer

from feanor.async_client import AsyncClient
from feanor.cli.output import error, render
from feanor.exceptions import FeanorAPIError

app = typer.Typer(help="Manage workflows.")

_COLS = ["id", "slug", "version", "execution_template_id", "created_at"]


def _ctx_opts(ctx: typer.Context) -> tuple[Optional[str], str, bool]:
    obj = ctx.obj or {}
    return obj.get("profile"), obj.get("output", "table"), obj.get("quiet", False)


@app.command("list")
def list_workflows(
    ctx: typer.Context,
    slug: Optional[str] = typer.Option(None, "--slug"),
) -> None:
    """List workflows."""
    profile, output_fmt, quiet = _ctx_opts(ctx)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            filters = {}
            if slug:
                filters["slug"] = slug
            results = await client.workflows.list(**filters)
        render(results, output_fmt, quiet, columns=_COLS)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def get(ctx: typer.Context, workflow_id: str = typer.Argument(...)) -> None:
    """Show details for a workflow."""
    profile, output_fmt, quiet = _ctx_opts(ctx)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            result = await client.workflows.get(workflow_id)
        render(result, output_fmt, quiet)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def run(
    ctx: typer.Context,
    workflow: str = typer.Argument(..., help="Workflow slug:version, e.g. my-etl:v3"),
    input: list[str] = typer.Option([], "--input", help="key=value pairs"),
) -> None:
    """Submit a workflow for execution. (Phase 2 feature — not yet available.)"""
    typer.echo(
        "Workflow execution submission is a Phase 2 feature. "
        "Once available, use: feanor executions list --workflow-id <id>",
        err=True,
    )
    raise typer.Exit(1)
