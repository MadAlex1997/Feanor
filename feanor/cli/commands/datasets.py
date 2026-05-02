import typer

app = typer.Typer(help="Manage datasets.")


@app.command("list")
def list_datasets() -> None:
    """List registered datasets."""
    raise NotImplementedError


@app.command()
def get(dataset_id: str) -> None:
    """Show details for a dataset."""
    raise NotImplementedError


@app.command()
def register(
    name: str = typer.Option(..., "--name"),
    source: str = typer.Option(..., "--source"),
) -> None:
    """Register a new dataset."""
    raise NotImplementedError


@app.command()
def delete(dataset_id: str) -> None:
    """Delete a dataset registration."""
    raise NotImplementedError
