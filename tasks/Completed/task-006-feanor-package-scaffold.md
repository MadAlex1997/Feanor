---
title: feanor package scaffold — pyproject.toml, directory structure, entry point
phase: 0
status: Completed
---

## Description

Create the `feanor/` Python package that ships both the SDK and CLI. This task
covers the project scaffold only: `pyproject.toml`, package directory layout,
empty module stubs, and the `feanor` CLI entry point wired to a minimal `typer`
app. Auth, Client, and config loading are implemented in subsequent tasks.

## Acceptance criteria

- [ ] A root `pixi.toml` is created at the repo root with:
      - `[feature.api.dependencies]` — api service deps (fastapi, uvicorn, sqlalchemy, etc.)
      - `[feature.sdk.dependencies]` — sdk/cli deps (typer, httpx, pydantic>=2, pyyaml, rich)
      - `[feature.dev.dependencies]` — dev tools (pytest, black, ruff)
      - `[feature.dev.pypi-dependencies]` — `feanor = { path = "feanor/", editable = true }`
      - `[environments]` — `default = ["dev"]`, `api = ["api", "dev"]`, `sdk = ["sdk", "dev"]`
      - `[tasks]` — `api-dev`, `test`, `lint` at minimum
- [ ] `feanor/pyproject.toml` defines package metadata only (no dev dependencies):
      - Name: `feanor`
      - Entry point: `feanor = feanor.cli:app`
      - Runtime dependencies: `typer`, `httpx`, `pydantic>=2`, `pyyaml`, `rich`
- [ ] Directory layout matches the architecture plan:
      ```
      feanor/
        __init__.py              # exports Client, AsyncClient
        client.py                # stub
        async_client.py          # stub
        auth.py                  # stub
        config.py                # stub
        http.py                  # stub
        models/
          __init__.py
          dataset.py             # stub
          workflow.py            # stub
          execution.py           # stub
          template.py            # stub
        resources/
          __init__.py
          datasets.py            # stub
          workflows.py           # stub
          executions.py          # stub
          templates.py           # stub
          system.py              # stub
        cli/
          __init__.py            # typer app
          commands/
            __init__.py
            auth.py              # stub
            datasets.py          # stub
            workflows.py         # stub
            executions.py        # stub
            query.py             # stub
            templates.py         # stub
            system.py            # stub
            infrastructure.py    # stub
      ```
- [ ] `feanor --help` runs and lists available command groups without errors.
- [ ] `feanor --version` prints the package version.
- [ ] `pixi install` at the repo root resolves all environments and installs `feanor`
      as an editable package — no separate virtualenv step needed.
- [ ] `pixi run lint` passes (`black --check` and `ruff check`) on all stub files.

## Dependencies

None — this is a standalone Python package with no runtime dependency on the
running Docker Compose stack.

## Notes

- Stubs should be valid Python (empty functions with `...` or `pass`, not just comments).
- `feanor/__init__.py` should have `from feanor.client import Client` and
  `from feanor.async_client import AsyncClient` — even if those classes are empty stubs.
- Use `typer` subcommands: each file in `cli/commands/` registers its own
  `typer.Typer()` and is mounted on the root app.
- The root `pixi.toml` is the single dependency manifest for the whole repo.
  Never add a `requirements.txt` or `conda.yaml` alongside it.
- `pixi.lock` must be committed — it pins the full resolved environment for
  reproducible CI and Docker builds.
