import typer

app = typer.Typer(help="Inspect executions.")


@app.command("list")
def list_executions() -> None:
    """List recent executions."""
    raise NotImplementedError


@app.command()
def get(execution_id: str) -> None:
    """Show execution details."""
    raise NotImplementedError


@app.command()
def logs(
    execution_id: str,
    follow: bool = typer.Option(False, "--follow", "-f"),
) -> None:
    """Stream execution logs."""
    raise NotImplementedError


@app.command()
def cancel(execution_id: str) -> None:
    """Cancel a running execution."""
    raise NotImplementedError
