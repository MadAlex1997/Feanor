from __future__ import annotations

import asyncio
from typing import Optional

import typer

from feanor.async_client import AsyncClient
from feanor.cli.output import error, render
from feanor.exceptions import FeanorAPIError

app = typer.Typer(help="Inspect executions.")

_COLS = ["id", "status", "workflow_id", "created_by", "created_at"]


def _ctx_opts(ctx: typer.Context) -> tuple[Optional[str], str, bool]:
    obj = ctx.obj or {}
    return obj.get("profile"), obj.get("output", "table"), obj.get("quiet", False)


@app.command("list")
def list_executions(
    ctx: typer.Context,
    status: Optional[str] = typer.Option(None, "--status"),
    workflow_id: Optional[str] = typer.Option(None, "--workflow-id"),
) -> None:
    """List recent executions."""
    profile, output_fmt, quiet = _ctx_opts(ctx)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            filters = {}
            if status:
                filters["status"] = status
            if workflow_id:
                filters["workflow_id"] = workflow_id
            results = await client.executions.list(**filters)
        render(results, output_fmt, quiet, columns=_COLS)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def get(ctx: typer.Context, execution_id: str = typer.Argument(...)) -> None:
    """Show execution details."""
    profile, output_fmt, quiet = _ctx_opts(ctx)

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            result = await client.executions.get(execution_id)
        render(result, output_fmt, quiet)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def logs(
    ctx: typer.Context,
    execution_id: str = typer.Argument(...),
    follow: bool = typer.Option(False, "--follow", "-f"),
) -> None:
    """Stream execution logs. (Phase 2 feature — not yet available.)"""
    typer.echo("Execution log streaming is a Phase 2 feature.", err=True)
    raise typer.Exit(1)


@app.command()
def cancel(ctx: typer.Context, execution_id: str = typer.Argument(...)) -> None:
    """Cancel a running execution. (Phase 2 feature — not yet available.)"""
    typer.echo("Execution cancellation is a Phase 2 feature.", err=True)
    raise typer.Exit(1)
