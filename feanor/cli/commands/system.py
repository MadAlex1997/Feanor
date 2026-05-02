from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.table import Table
from rich import print as rprint

from feanor.async_client import AsyncClient
from feanor.config import load_config

app = typer.Typer(help="Platform system commands.")


def _get_profile(ctx: typer.Context) -> Optional[str]:
    return (ctx.obj or {}).get("profile")


@app.command()
def health(ctx: typer.Context) -> None:
    """Check platform health."""
    profile_name = _get_profile(ctx)

    async def _run() -> None:
        async with AsyncClient(profile_name) as client:
            result = await client.system.health()
        table = Table("Key", "Value")
        table.add_row("status", result.status)
        rprint(table)

    asyncio.run(_run())


@app.command()
def ready(ctx: typer.Context) -> None:
    """Check platform readiness (DB connectivity)."""
    profile_name = _get_profile(ctx)

    async def _run() -> None:
        async with AsyncClient(profile_name) as client:
            result = await client.system.ready()
        table = Table("Key", "Value")
        table.add_row("status", result.status)
        rprint(table)

    asyncio.run(_run())
