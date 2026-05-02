import typer

app = typer.Typer(help="Platform system commands.")


@app.command()
def health() -> None:
    """Check platform health."""
    raise NotImplementedError


@app.command()
def ready() -> None:
    """Check platform readiness."""
    raise NotImplementedError
