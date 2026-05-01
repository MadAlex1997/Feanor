---
title: feanor config loading — ~/.feanor/config.yaml and --profile flag
phase: 0
status: Pending
---

## Description

Implement `feanor/config.py`: load and parse `~/.feanor/config.yaml`, expose the
active profile, and wire the `--profile` flag into the CLI. Config loading must
also respect the `FEANOR_PROFILE` and `FEANOR_API_URL` environment variable
overrides.

## Acceptance criteria

- [ ] `feanor/config.py` exports a `load_config(profile: str | None = None) -> Profile` function.
- [ ] `Profile` is a Pydantic v2 model with fields:
      `api_url: str`, `keycloak_url: str`, `realm: str`,
      and optional `token: str | None`, `refresh_token: str | None`,
      `token_expires_at: datetime | None`.
- [ ] Config file path: `~/.feanor/config.yaml`. If the file does not exist,
      a default `local` profile is returned pointing at `http://localhost:8000`
      and `http://localhost:8080`.
- [ ] `FEANOR_PROFILE` env var overrides the `default_profile` key in the YAML.
- [ ] `FEANOR_API_URL` env var overrides the `api_url` of the resolved profile.
- [ ] `--profile <name>` CLI flag takes precedence over `FEANOR_PROFILE` and the
      YAML default. It must be available on every CLI command (defined on the root app).
- [ ] `feanor whoami` prints the active profile name and `api_url`.
- [ ] `load_config` raises a clear error (not a raw `KeyError`) if a named profile
      does not exist in the config file.
- [ ] Unit tests cover: missing file → default profile, env var override,
      unknown profile error, `--profile` flag propagation.

## Dependencies

- task-006 (package scaffold must exist)

## Notes

- Profile resolution order (highest to lowest priority):
  `--profile` flag > `FEANOR_PROFILE` env > `default_profile` in YAML > `local` hardcoded default.
- `FEANOR_API_URL` only overrides `api_url`; all other profile fields come from the YAML.
- The config file also doubles as a token cache (written by `TokenManager` in task-007).
  `load_config` should read whatever is stored; `TokenManager` is responsible for writing.
  Avoid circular imports by keeping config loading a pure read operation.
- Create `~/.feanor/` directory if it does not exist when writing the config file
  (but not on read — a missing directory is equivalent to a missing file).
