---
title: Auth role enforcement — FastAPI dependency for Keycloak roles
phase: 1
status: Pending
---

## Description

Implement a FastAPI dependency that reads the forwarded identity headers set by
Traefik's forwardAuth middleware (`X-Feanor-Subject`, `X-Feanor-Roles`) and
enforces that the caller holds at least one of the required Keycloak roles.
This is the single auth check used by every protected route handler.

## Acceptance criteria

- [ ] `api/app/deps.py` exports:
      - `CurrentUser` — Pydantic model with `subject: str` and `roles: list[str]`.
      - `get_current_user` — FastAPI dependency that reads `X-Feanor-Subject`
        and `X-Feanor-Roles` headers, returning `CurrentUser`. Returns `401`
        if either header is missing (Traefik should always set them on /v1/* requests).
      - `require_roles(*roles: str)` — returns a FastAPI dependency that calls
        `get_current_user` and raises `403` if none of the caller's roles are in
        the required set. Usage: `Depends(require_roles("analyst", "engineer"))`.
- [ ] Role constants are defined in `api/app/deps.py`:
      `PLATFORM_ADMIN`, `ENGINEER`, `ANALYST`, `SERVICE_ACCOUNT`.
- [ ] Unit tests cover: valid roles pass, missing header returns 401, wrong role
      returns 403, multiple allowed roles — any one suffices.

## Dependencies

- task-005 (Traefik sets the forwarded headers; task-011 reads them)
- task-010 (app structure must exist before adding deps)

## Notes

- Do NOT re-verify the JWT in these handlers — Traefik already verified the
  signature. The headers are trusted because they come from within the Docker
  network after Traefik's forwardAuth check.
- In local dev without Traefik (e.g., running `uvicorn` directly), these headers
  won't be set. That is expected and acceptable — dev testing should go through
  Traefik, or tests should inject the headers explicitly.
- `require_roles` should accept multiple roles and pass if the caller has ANY of
  them — not all. This makes it easy to express "engineer or admin".
- Role string values must match Keycloak role names exactly (lowercase with
  underscores): `platform_admin`, `engineer`, `analyst`, `service_account`.
