from __future__ import annotations

from typing import Optional

import typer

from feanor.cli.commands import (
    auth,
    datasets,
    executions,
    infrastructure,
    system,
    templates,
    workflows,
)
from feanor.cli.commands.query import run_query

app = typer.Typer(
    name="feanor",
    help="Fëanor federated data and compute platform CLI.",
    no_args_is_help=True,
)

# Global options injected before every command.
_profile_option = typer.Option(None, "--profile", "-p", help="Config profile name.", envvar="FEANOR_PROFILE")
_output_option = typer.Option("table", "--output", "-o", help="Output format: table | json | yaml.")


@app.callback()
def main(
    ctx: typer.Context,
    profile: Optional[str] = _profile_option,
    output: str = _output_option,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["profile"] = profile
    ctx.obj["output"] = output


app.add_typer(auth.app, name="auth")
app.add_typer(datasets.app, name="datasets")
app.add_typer(workflows.app, name="workflows")
app.add_typer(executions.app, name="executions")
app.command("query")(run_query)
app.add_typer(templates.app, name="templates")
app.add_typer(system.app, name="system")
app.add_typer(infrastructure.app, name="infrastructure")
