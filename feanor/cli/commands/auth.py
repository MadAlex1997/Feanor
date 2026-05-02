from __future__ import annotations

from typing import Optional

import typer

from feanor.config import load_config, save_config

app = typer.Typer(help="Authentication commands.")


@app.command()
def login(ctx: typer.Context) -> None:
    """Authenticate via device flow and cache the token."""
    profile_name: Optional[str] = (ctx.obj or {}).get("profile")
    from feanor.auth import TokenManager

    profile = load_config(profile_name)
    try:
        tm = TokenManager(profile)
        token = tm.get_token()
        typer.echo("Login successful.")
    except Exception as exc:
        typer.echo(f"Login failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command()
def logout(ctx: typer.Context) -> None:
    """Remove the cached token for the active profile."""
    profile_name: Optional[str] = (ctx.obj or {}).get("profile")
    profile = load_config(profile_name)
    profile.token = None
    profile.refresh_token = None
    save_config(profile)
    typer.echo(f"Logged out profile '{profile.name}'.")


@app.command()
def whoami(ctx: typer.Context) -> None:
    """Print the active profile name and API URL."""
    profile_name: Optional[str] = (ctx.obj or {}).get("profile")
    profile = load_config(profile_name)
    typer.echo(f"Profile : {profile.name}")
    typer.echo(f"API URL : {profile.api_url}")
    typer.echo(f"Keycloak: {profile.keycloak_url}")
    typer.echo(f"Realm   : {profile.realm}")
