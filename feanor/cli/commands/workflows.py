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
_EXEC_COLS = ["id", "workflow_id", "status", "created_by", "created_at", "started_at", "ended_at"]


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
    workflow: str = typer.Argument(..., help="Workflow slug:version or UUID"),
    input: list[str] = typer.Option([], "--input", help="key=value input pairs"),
    wait: bool = typer.Option(False, "--wait", help="Block until execution completes"),
    timeout: int = typer.Option(60, "--timeout", help="Timeout in seconds (only with --wait)"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
) -> None:
    """Submit a workflow for execution."""
    profile, output_fmt, quiet = _ctx_opts(ctx)
    if output:
        output_fmt = output

    if timeout != 60 and not wait:
        typer.echo("Warning: --timeout has no effect without --wait", err=True)

    inputs: dict = {}
    for item in input:
        if "=" not in item:
            raise typer.BadParameter(f"input must be key=value, got: {item!r}", param_hint="--input")
        k, v = item.split("=", 1)
        inputs[k] = v

    async def _run() -> None:
        async with AsyncClient(profile) as client:
            if wait:
                typer.echo("Waiting for execution to complete...", err=True)
            result = await client.executions.submit(
                workflow=workflow,
                inputs=inputs or None,
                wait=wait,
                timeout=timeout,
            )
        render(result, output_fmt, quiet, columns=_EXEC_COLS)

    try:
        asyncio.run(_run())
    except FeanorAPIError as exc:
        if exc.status_code == 408:
            typer.echo(
                f"Execution timed out. Use `feanor executions get <id>` to check status.",
                err=True,
            )
            raise typer.Exit(1)
        error(exc.message)
        raise typer.Exit(1)
    except ValueError as exc:
        error(str(exc))
        raise typer.Exit(1)
