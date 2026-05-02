from __future__ import annotations

import asyncio
import time
from typing import Optional

import typer

from feanor.async_client import AsyncClient
from feanor.cli.output import error, render
from feanor.exceptions import FeanorAPIError

app = typer.Typer(help="Inspect executions.")

_COLS = ["id", "workflow_id", "status", "created_by", "created_at", "started_at", "ended_at"]


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
        render(result, output_fmt, quiet, columns=_COLS)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def cancel(
    ctx: typer.Context,
    execution_id: str = typer.Argument(...),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Cancel a running or pending execution."""
    profile, output_fmt, quiet = _ctx_opts(ctx)
    if output:
        output_fmt = output

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            result = await client.executions.cancel(execution_id)
        typer.echo("Execution cancelled.")
        render(result, output_fmt, quiet, columns=_COLS)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        if exc.status_code == 409:
            error(exc.message)
            raise typer.Exit(1)
        if exc.status_code == 404:
            error("Execution not found.")
            raise typer.Exit(2)
        error(exc.message)
        raise typer.Exit(1)


@app.command()
def logs(
    ctx: typer.Context,
    execution_id: str = typer.Argument(...),
    tail: Optional[int] = typer.Option(None, "--tail", "-n"),
    follow: bool = typer.Option(False, "--follow", "-f"),
    interval: float = typer.Option(2.0, "--interval", min=1.0),
) -> None:
    """Show or follow execution logs."""
    profile, _, _ = _ctx_opts(ctx)

    _TERMINAL = {"succeeded", "failed", "cancelled"}

    async def _run_once() -> None:
        async with AsyncClient(profile) as client:
            result = await client.executions.logs(execution_id, tail=tail)
        if result is None:
            typer.echo("No logs available yet.", err=True)
        else:
            typer.echo(result)

    async def _run_follow() -> None:
        async with AsyncClient(profile) as client:
            log_text = await client.executions.logs(execution_id, follow=True)
            if log_text:
                typer.echo(log_text, nl=False)
            exe = await client.executions.get(execution_id)
            if exe.status == "failed":
                raise typer.Exit(1)

    try:
        if follow:
            asyncio.run(_run_follow())
        else:
            asyncio.run(_run_once())
    except FeanorAPIError as exc:
        error(exc.message)
        raise typer.Exit(1)
