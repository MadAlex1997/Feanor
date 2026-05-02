"""Shared output rendering for all CLI commands."""
from __future__ import annotations

import json
import sys
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


def _to_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return obj
    return vars(obj)


def render(
    data: Any,
    output_fmt: str = "table",
    quiet: bool = False,
    columns: list[str] | None = None,
) -> None:
    if quiet:
        return

    items: list[dict]
    if isinstance(data, list):
        items = [_to_dict(d) for d in data]
    else:
        items = [_to_dict(data)]

    if output_fmt == "json":
        sys.stdout.write(json.dumps(items if isinstance(data, list) else items[0], indent=2, default=str))
        sys.stdout.write("\n")
        return

    if output_fmt == "yaml":
        sys.stdout.write(yaml.safe_dump(items if isinstance(data, list) else items[0], default_flow_style=False))
        return

    # table
    if not items:
        console.print("[dim]No results.[/dim]")
        return

    cols = columns or list(items[0].keys())
    table = Table(*cols, show_header=True, header_style="bold")
    for item in items:
        table.add_row(*[str(item.get(c, "")) for c in cols])
    console.print(table)


def error(msg: str) -> None:
    err_console.print(f"[red]error:[/red] {msg}")
