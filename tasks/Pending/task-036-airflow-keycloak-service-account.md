---
title: Airflow service account in Keycloak — client credentials + env wiring
phase: 4
status: Pending
---

## Description

Create a Keycloak service account client for Airflow and wire its credentials
into the Docker Compose stack so that DAGs can authenticate to the Fëanor control
plane API using the `service_account` role via client credentials grant. No DAG
code is written here — this task is auth plumbing only.

## Acceptance criteria

### Keycloak configuration

- [ ] A new confidential client in the `feanor` realm:
      - Client ID: `airflow`
      - Client authentication: ON (confidential)
      - Service accounts enabled: ON
      - Standard flow: OFF, Direct access grants: OFF
      - Only grant type: `client_credentials`

- [ ] The `airflow` service account is assigned the `service_account` realm role
      in Keycloak (same role used by execution workers).

- [ ] The Keycloak realm export file (`infra/keycloak/feanor-realm.json`) updated
      to include the new `airflow` client definition so `docker compose up` from
      scratch recreates it without manual Keycloak UI steps.

- [ ] `.env.example` updated with:
      ```
      AIRFLOW_FEANOR_CLIENT_ID=airflow
      AIRFLOW_FEANOR_CLIENT_SECRET=<placeholder — set real value in .env>
      FEANOR_KEYCLOAK_URL=http://keycloak:8080
      FEANOR_REALM=feanor
      ```

### Docker Compose wiring

- [ ] The `airflow-webserver` and `airflow-scheduler` services (via the shared
      YAML anchor from task-035) receive the following additional environment
      variables:
      ```
      FEANOR_API_URL=http://api:8000
      FEANOR_CLIENT_ID=${AIRFLOW_FEANOR_CLIENT_ID}
      FEANOR_CLIENT_SECRET=${AIRFLOW_FEANOR_CLIENT_SECRET}
      FEANOR_KEYCLOAK_URL=${FEANOR_KEYCLOAK_URL}
      FEANOR_REALM=${FEANOR_REALM}
      ```

- [ ] The `feanor` SDK's `TokenManager` in `feanor/auth.py` reads these env vars
      and performs the client credentials grant against Keycloak. Verify it already
      handles this path; if not, add support:
      - If `FEANOR_CLIENT_ID` and `FEANOR_CLIENT_SECRET` are set, acquire a token
        via `POST {keycloak_url}/realms/{realm}/protocol/openid-connect/token`
        with `grant_type=client_credentials`.
      - Cache the token; refresh before expiry.

### Smoke test

- [ ] A manual smoke-test procedure documented in task notes (not automated):
      1. `docker exec -it feanor-airflow-scheduler-1 bash`
      2. `python -c "from feanor import Client; c = Client(); print(c.system.health())"`
      3. Should print `{"status": "ok"}` without prompting for login.

- [ ] The same test run as a pytest fixture-level check in `tests/conftest.py`
      using environment variables:
      - Add a `feanor_service_client` fixture (session-scoped) that creates a
        `Client` using `FEANOR_CLIENT_ID` / `FEANOR_CLIENT_SECRET` env vars.
      - Skip with `pytest.skip` if the vars are not set (CI without Keycloak).

## Dependencies

- task-002 (Keycloak realm config — existing realm setup and export process)
- task-007 (auth module — TokenManager must support client credentials)
- task-035 (Airflow in Docker Compose — services must exist to inject env vars)

## Notes

- The client secret for `airflow` must be generated in the Keycloak UI or via
  the admin REST API, then saved to `.env`. It cannot be committed to the repo.
  The realm export includes the client definition but not the secret — document
  this in a comment in `infra/keycloak/feanor-realm.json`.
- If the Keycloak realm export format does not support the `airflow` client
  natively (e.g. secrets are masked in exports), add a `infra/keycloak/README.md`
  section with the manual steps to configure the client after `docker compose up`.
- `FEANOR_KEYCLOAK_URL` and `FEANOR_REALM` are new env vars. Ensure the `feanor`
  SDK `config.py` reads them (alongside the existing `FEANOR_API_URL`). Fall back
  to profile values from `~/.feanor/config.yaml` if not set.
- The `service_account` role in Keycloak must already exist from Phase 0 (task-002).
  This task only assigns it to the new client's service account, it does not create
  the role.
