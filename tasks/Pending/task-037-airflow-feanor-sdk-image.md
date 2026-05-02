---
title: Custom Airflow Docker image with feanor SDK installed
phase: 4
status: Pending
---

## Description

Build a custom Airflow Docker image that has the `feanor` Python package installed.
This lets DAG authors `from feanor import Client` directly in task callables without
any additional setup. The image is built from the local source tree so that changes
to the `feanor` package are picked up on the next `docker compose build`.

## Acceptance criteria

### Dockerfile

- [ ] `airflow/Dockerfile` created:
      ```dockerfile
      FROM apache/airflow:2.9
      USER root
      COPY ../feanor /opt/feanor-src
      RUN pip install --no-cache-dir /opt/feanor-src
      USER airflow
      ```
      The `COPY` uses the build context set in `docker-compose.yml` (repo root),
      so the path becomes `feanor/` relative to that context.

- [ ] `airflow/.dockerignore` created to exclude test artifacts:
      ```
      __pycache__
      *.pyc
      .pytest_cache
      dist/
      *.egg-info/
      ```

### Docker Compose update

- [ ] `docker-compose.yml` updated so `airflow-webserver` and `airflow-scheduler`
      (via the shared anchor from task-035) use a `build:` stanza:
      ```yaml
      build:
        context: .
        dockerfile: airflow/Dockerfile
      image: feanor-airflow:local
      ```
      The `image:` tag allows `docker compose push` to work if needed later.

- [ ] `docker compose build airflow-webserver` completes without errors.

- [ ] The built image passes a validation check:
      ```bash
      docker run --rm feanor-airflow:local python -c "from feanor import Client; print('ok')"
      ```
      Prints `ok`.

### pixi integration

- [ ] `pixi.toml` (root) has a task to build the Airflow image:
      ```toml
      [tool.pixi.tasks]
      build-airflow = "docker compose build airflow-webserver"
      ```
      (Or use the existing task convention in the project.)

### Verification

- [ ] `docker compose up --build` starts all services including the rebuilt Airflow
      image.

- [ ] Inside the running scheduler container:
      ```bash
      docker exec feanor-airflow-scheduler-1 python -c \
        "import feanor; print(feanor.__version__)"
      ```
      Prints the package version without import errors.

- [ ] `README.md` updated: add a note that `docker compose up --build` is required
      after changes to the `feanor/` package to pick them up in Airflow.

## Dependencies

- task-035 (Airflow Docker Compose services must exist)
- task-006 (feanor package scaffold — must be installable via pip)

## Notes

- Install as a regular pip package (not editable `-e`) inside the container image.
  Editable installs inside Docker require bind mounts and complicate multi-stage
  builds. For local development, developers rebuild the image when they change
  SDK code (`docker compose build`).
- The Airflow base image runs as user `airflow` (UID 50000). The `pip install`
  step must run as root, then switch back. The Dockerfile above does this
  correctly — do not change the user ordering.
- If `feanor` has optional extras (e.g. `feanor[worker]`), install the base
  package only here. Worker extras are installed in the worker image (task-022).
- If pixi manages the feanor package dependencies, the Dockerfile may need to
  install pixi or use a pre-built wheel. Prefer generating a wheel:
  `pixi run python -m build --wheel` and copying it into the image.
  Add a `build-wheel` task to `pixi.toml` if needed.
