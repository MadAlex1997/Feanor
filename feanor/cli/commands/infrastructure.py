import typer
from pathlib import Path

app = typer.Typer(help="Custom infrastructure (escape hatch).")


@app.command()
def apply(file: Path = typer.Option(..., "--file", "-f", help="Terraform file or zip to apply")) -> None:
    """Submit custom Terraform for plan + apply (platform_admin only)."""
    raise NotImplementedError


@app.command()
def destroy(custom_id: str) -> None:
    """Destroy a previously applied custom infrastructure resource."""
    raise NotImplementedError
