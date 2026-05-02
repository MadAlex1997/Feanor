---
title: Airflow Fëanor connection type and hook
phase: 4
status: Pending
---

## Description

Create a custom Airflow hook (`FeanorHook`) that wraps the `feanor` SDK `Client`
and sources connection parameters from an Airflow Connection record. DAG authors
call `FeanorHook().get_client()` instead of constructing a `Client` manually,
keeping credentials out of DAG code and making the connection configurable per
Airflow environment. This is the foundation that the example DAGs in tasks 039
and 040 build on.

## Acceptance criteria

### Hook implementation

- [ ] `dags/hooks/feanor_hook.py` created:
      - Class `FeanorHook(BaseHook)`.
      - `conn_id` parameter (default: `"feanor_default"`).
      - `get_client() -> feanor.Client` method:
        1. Fetches the Airflow Connection with the given `conn_id`.
        2. Reads `conn.host` as `api_url` (e.g. `http://api:8000`).
        3. Reads `conn.login` as `client_id`, `conn.password` as `client_secret`.
        4. Reads `conn.extra_dejson.get("keycloak_url")` and
           `conn.extra_dejson.get("realm")` (fallback to env vars
           `FEANOR_KEYCLOAK_URL` and `FEANOR_REALM`).
        5. Constructs and returns a `feanor.Client` configured with these values.
      - `conn_type = "feanor"` class attribute.
      - `hook_name = "Fëanor"` class attribute.

- [ ] `dags/hooks/__init__.py` created (empty).

### Airflow connection registration

- [ ] A connection-setup script `airflow/setup_connections.py` that can be run
      inside the Airflow container to register the default connection:
      ```bash
      airflow connections add feanor_default \
        --conn-type generic \
        --conn-host "${FEANOR_API_URL}" \
        --conn-login "${FEANOR_CLIENT_ID}" \
        --conn-password "${FEANOR_CLIENT_SECRET}" \
        --conn-extra "{\"keycloak_url\": \"${FEANOR_KEYCLOAK_URL}\", \"realm\": \"${FEANOR_REALM}\"}"
      ```

- [ ] The `airflow-init` service in `docker-compose.yml` (task-035) updated to
      also run `setup_connections.py` after `db migrate`, so the connection is
      present on every fresh `docker compose up`.

- [ ] The `airflow-init` command becomes:
      ```bash
      airflow db migrate &&
      airflow users create --username admin --password "${AIRFLOW_ADMIN_PASSWORD}" \
        --firstname Feanor --lastname Admin --role Admin --email admin@feanor.local &&
      python /opt/airflow/setup_connections.py
      ```

### Tests

- [ ] Unit test for `FeanorHook.get_client()`:
      - Mock `BaseHook.get_connection` to return a synthetic Connection object.
      - Assert the returned `Client` has the correct `api_url` and that
        `TokenManager` was initialised with the correct `client_id` / `client_secret`.
      - Test lives in `tests/test_airflow_hook.py`.

- [ ] Test is runnable without a live Airflow instance (mock all Airflow imports).

## Dependencies

- task-035 (Airflow Docker Compose — `airflow-init` service to extend)
- task-036 (Keycloak service account — credentials that the hook reads)
- task-037 (Airflow image with feanor SDK — `FeanorHook` imports `feanor.Client`)

## Notes

- Airflow Connections use `conn_type = "generic"` when no matching UI plugin is
  registered. Registering a proper `conn_type = "feanor"` with a UI form requires
  an Airflow plugin. For MVP, `"generic"` is sufficient. A plugin can be added
  in Phase 6.
- The `extra` field of an Airflow Connection is a JSON string. Use
  `conn.extra_dejson` (a dict) rather than parsing it manually.
- Keep `FeanorHook` thin: it only constructs the `Client`. Retry logic, token
  refresh, and error handling all live in the `feanor` SDK. Do not duplicate them
  here.
- `dags/hooks/` is on the `sys.path` that Airflow loads for DAGs. Imports within
  DAGs should be `from hooks.feanor_hook import FeanorHook`.
