---
title: Keycloak realm configuration — roles, dev users, service account
phase: 0
status: Completed
---

## Description

Configure the `feanor` Keycloak realm with all roles, a set of dev users for
local testing, and the Airflow service account. This should be fully automated
so the realm is reproducible — no manual click-through in the Keycloak UI.

## Acceptance criteria

- [ ] Realm `feanor` exists and is importable via a `realm-export.json` file
      (stored in `keycloak/` in the repo).
- [ ] Four roles exist: `platform_admin`, `engineer`, `analyst`, `service_account`.
- [ ] Dev users exist (one per role) with known passwords suitable for local testing:
      - `admin@feanor.local` → `platform_admin`
      - `engineer@feanor.local` → `engineer`
      - `analyst@feanor.local` → `analyst`
- [ ] A service account client `airflow-sa` exists with:
      - Grant type: client credentials
      - Role: `service_account`
      - Client secret stored in `.env.example` / Docker Compose env.
- [ ] A client `feanor-cli` exists configured for device authorization flow.
- [ ] A client `feanor-sdk` exists configured for authorization code + PKCE.
- [ ] Token lifetimes: access token 15 min, refresh token 8 hours.
- [ ] Realm import is applied automatically on Keycloak container startup
      (via `KC_IMPORT` or mounted realm JSON).

## Dependencies

- task-001 (Keycloak container must be running)

## Notes

- Realm JSON can be exported from a manually configured instance and committed.
  Alternatively, use the Keycloak Admin REST API scripted via a startup hook.
- Do not commit real secrets — `.env.example` shows the shape; `.env` (gitignored)
  holds real values.
- Dev mode Keycloak does not persist data across restarts unless a volume is
  mounted at `/opt/keycloak/data`.
