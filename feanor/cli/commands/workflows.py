import typer

app = typer.Typer(help="Manage workflows.")


@app.command("list")
def list_workflows() -> None:
    """List workflows."""
    raise NotImplementedError


@app.command()
def get(workflow_id: str) -> None:
    """Show details for a workflow."""
    raise NotImplementedError


@app.command()
def run(
    workflow: str = typer.Argument(..., help="Workflow ID, e.g. my-etl:v3"),
    input: list[str] = typer.Option([], "--input", help="key=value pairs"),
) -> None:
    """Submit a workflow for execution."""
    raise NotImplementedError
