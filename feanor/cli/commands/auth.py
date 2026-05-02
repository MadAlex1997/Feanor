import typer

app = typer.Typer(help="Authentication commands.")


@app.command()
def login() -> None:
    """Authenticate via device flow and cache the token."""
    raise NotImplementedError


@app.command()
def logout() -> None:
    """Remove the cached token for the active profile."""
    raise NotImplementedError


@app.command()
def whoami() -> None:
    """Print the active profile name and API URL."""
    raise NotImplementedError
