import typer

app = typer.Typer(help="Manage execution templates.")


@app.command("list")
def list_templates() -> None:
    """List registered execution templates."""
    raise NotImplementedError


@app.command()
def get(template_id: str) -> None:
    """Show details for an execution template."""
    raise NotImplementedError
