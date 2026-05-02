---
title: feanor auth module — TokenManager (acquire, cache, refresh)
phase: 0
status: Completed
---

## Description

Implement `feanor/auth.py`: the `TokenManager` class that handles all credential
acquisition, caching, and refresh. This is the single auth layer for both the
SDK and CLI — no other module should make Keycloak requests directly.

Three credential strategies must be supported, tried in this order:

1. `FEANOR_TOKEN` env var — use the token as-is (no refresh).
2. `FEANOR_CLIENT_ID` + `FEANOR_CLIENT_SECRET` — client credentials grant.
3. Stored token in `~/.feanor/config.yaml` (profile-scoped) — with refresh.
4. Device authorization flow — interactive browser login (CLI fallback).

## Acceptance criteria

- [ ] `TokenManager` is importable from `feanor.auth`.
- [ ] `TokenManager(profile: Profile)` accepts a config profile (from task-009).
- [ ] `TokenManager.get_token() -> str` returns a valid access token, transparently
      refreshing if the cached token is within 60 seconds of expiry.
- [ ] Client credentials flow: exchanges `client_id` / `client_secret` against
      `POST /realms/feanor/protocol/openid-connect/token`.
- [ ] Device flow: prints the user code and verification URL, polls the token
      endpoint until the user completes login, then caches the token pair.
- [ ] Tokens are cached in `~/.feanor/config.yaml` under the active profile
      (access token + refresh token + expiry timestamp).
- [ ] `FEANOR_TOKEN` env var bypasses all flow logic and is returned directly.
- [ ] If `FEANOR_TOKEN` is set but expired (JWT `exp` check), a warning is logged
      and the token is still returned (caller may get a 401 — not our problem).
- [ ] Unit tests cover: credential resolution order, token refresh trigger,
      client credentials exchange (httpx mocked), expired-token warning.

## Dependencies

- task-006 (package scaffold must exist)
- task-002 (Keycloak realm must be configured for integration testing against the local stack)

## Notes

- Use `httpx` (already in dependencies) for all token endpoint calls — no `requests`.
- JWT expiry check should use the `exp` claim decoded without signature verification
  (we trust the token we just fetched from Keycloak).
- Device flow polling must respect the `interval` field from the device auth response.
- Do not persist `FEANOR_CLIENT_SECRET` to disk under any circumstances.
- The token cache in `config.yaml` must use a profile-scoped key so multiple
  profiles don't collide.
