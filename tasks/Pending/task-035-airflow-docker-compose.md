---
title: Airflow in Docker Compose with LocalExecutor
phase: 4
status: Pending
---

## Description

Add Apache Airflow 2.9 to the local MVP Docker Compose stack using LocalExecutor.
This task is infrastructure only — no DAGs are written here. The result is a
running Airflow webserver and scheduler backed by the existing PostgreSQL service,
with a mounted DAGs directory and a persistent `feanor-logs` volume for task logs.

## Acceptance criteria

- [ ] `docker-compose.yml` updated with three new services: `airflow-init`,
      `airflow-webserver`, and `airflow-scheduler`.

- [ ] `airflow-init` service — runs once at startup, exits 0:
      - Image: `apache/airflow:2.9`
      - Command: `bash -c "airflow db migrate && airflow users create ..."`
      - Creates admin user: username `admin`, password from `AIRFLOW_ADMIN_PASSWORD`
        env var (default: `admin` in `.env.example`).
      - `restart: on-failure`

- [ ] `airflow-webserver` service:
      - Image: `apache/airflow:2.9` (or custom image from task-037 once that lands —
        use a `build:` stanza pointing at `./airflow/Dockerfile` with a fallback
        `image:` tag so it works before task-037).
      - Command: `airflow webserver`
      - Port: `8081:8080` on the host (Trino occupies host 8080 from task-028).
      - Mounts: `./dags:/opt/airflow/dags:ro`, `./airflow/logs:/opt/airflow/logs`
      - `depends_on: [airflow-init, postgres]`
      - Health check: `GET http://localhost:8080/health` returns `200`.

- [ ] `airflow-scheduler` service:
      - Image: same as webserver (keep in sync via YAML anchor `&airflow-common`).
      - Command: `airflow scheduler`
      - Same mounts as webserver.
      - `depends_on: [airflow-init, postgres]`

- [ ] Shared environment variables (via YAML anchor or `env_file`) on both
      `airflow-webserver` and `airflow-scheduler`:
      ```
      AIRFLOW__CORE__EXECUTOR=LocalExecutor
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/airflow
      AIRFLOW__CORE__FERNET_KEY=${AIRFLOW_FERNET_KEY}
      AIRFLOW__CORE__LOAD_EXAMPLES=False
      AIRFLOW__WEBSERVER__SECRET_KEY=${AIRFLOW_SECRET_KEY}
      AIRFLOW__LOGGING__BASE_LOG_FOLDER=/opt/airflow/logs
      ```

- [ ] `postgres` service updated: the `POSTGRES_DB` env var sets the default DB
      to `feanor`. The `airflow` database must be created separately. Add an
      `init-db.sql` script mounted as a Docker entrypoint init file:
      ```sql
      CREATE DATABASE airflow;
      ```
      Mount at `/docker-entrypoint-initdb.d/init-db.sql`.

- [ ] `.env.example` updated with:
      ```
      AIRFLOW_FERNET_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
      AIRFLOW_SECRET_KEY=<random string>
      AIRFLOW_ADMIN_PASSWORD=admin
      ```

- [ ] `dags/` directory created at the repo root (empty, with a `.gitkeep`).

- [ ] `airflow/logs/` directory created (add to `.gitignore`).

- [ ] `docker compose up` with the updated file starts successfully. All three
      Airflow services healthy.

- [ ] Airflow web UI accessible at `http://localhost:8081`. Login with
      `admin`/`admin` succeeds. DAGs list is empty (examples hidden).

- [ ] `README.md` updated with Airflow access instructions (URL, default credentials,
      how to add DAGs by dropping files in `./dags/`).

## Dependencies

- task-001 (Docker Compose stack — postgres must be running)
- task-028 (Trino uses host port 8080; Airflow webserver must use 8081)

## Notes

- Use a YAML anchor (`x-airflow-common: &airflow-common`) in `docker-compose.yml`
  to share image, environment, mounts, and dependencies between webserver and
  scheduler — avoids duplication and drift.
- LocalExecutor runs tasks as subprocesses of the scheduler. No Celery or Redis
  needed. Suitable for local MVP.
- Generate a real Fernet key for `.env.example` using the command shown above and
  commit only the example value (e.g. a generated-but-not-secret placeholder).
  Real keys go in `.env` (gitignored).
- Airflow startup can take 30–60 seconds after `db migrate`. Set
  `start_period: 90s` on health checks to avoid false negatives.
- The `airflow-init` service must complete before the webserver and scheduler
  start. Use `condition: service_completed_successfully` in `depends_on`.
