import typer

app = typer.Typer(help="Run federated SQL queries via Trino.")


@app.command()
def run(sql: str = typer.Argument(..., help="SQL statement to execute")) -> None:
    """Execute a Trino query and print results."""
    raise NotImplementedError
