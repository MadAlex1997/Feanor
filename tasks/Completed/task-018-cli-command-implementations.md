---
title: CLI command implementations — all feanor resource commands
phase: 1
status: Pending
---

## Description

Implement the stub CLI command bodies from task-006, replacing `raise NotImplementedError`
with real calls to the SDK. All commands must support `--output table|json|yaml`
(inherited from the root app) and `--quiet` (machine-readable, exit code only).

## Acceptance criteria

**datasets:**
- [ ] `feanor datasets list [--created-by <subject>]` — table of id, name, source_ref, created_at.
- [ ] `feanor datasets get <id>` — full dataset detail.
- [ ] `feanor datasets register --name <n> --source <s> [--schema-hints <json>]` — prints the new dataset.
- [ ] `feanor datasets delete <id>` — confirms deletion (or exits silently with `--quiet`).

**workflows:**
- [ ] `feanor workflows list [--slug <slug>]` — table of id, slug, version, template, created_at.
- [ ] `feanor workflows get <id>` — full workflow detail including template.
- [ ] `feanor workflows run <slug:version> [--input key=value ...]` — submits execution,
      prints execution ID. (Delegates to Phase 2's `executions.submit`; prints a
      helpful "not yet implemented" error until then.)

**executions:**
- [ ] `feanor executions list [--status <s>] [--workflow-id <id>]` — table view.
- [ ] `feanor executions get <id>` — full execution detail.

**templates:**
- [ ] `feanor templates list [--type <t>]` — table of id, name, type.
- [ ] `feanor templates get <id>` — full template detail.

**auth:**
- [ ] `feanor login` — triggers device flow via `TokenManager`, prints success.
- [ ] `feanor auth whoami` — already implemented in task-009 (verify still works).
- [ ] `feanor auth logout` — removes token fields from `~/.feanor/config.yaml`.

**system:**
- [ ] `feanor system health` — already implemented in task-008 (verify still works).
- [ ] `feanor system ready` — calls `GET /ready`, prints status.

**Output formatting:**
- [ ] `--output table` (default): rich Table with column headers.
- [ ] `--output json`: `json.dumps(data, indent=2)` to stdout.
- [ ] `--output yaml`: `yaml.safe_dump(data)` to stdout.
- [ ] `--quiet`: suppress output, use exit code only (0 = success, 1 = error).

## Dependencies

- task-017 (SDK methods must be implemented before CLI can call them)

## Notes

- CLI commands call the SDK's async methods directly using `asyncio.run(...)`.
  Do not add a sync adapter — one `asyncio.run` per top-level CLI command is fine.
- Use a shared `_render(data, output_fmt)` helper in `feanor/cli/output.py` to
  avoid duplicating table/json/yaml logic across every command.
- For `--output table`, flatten nested objects to their ID or a short summary.
  Full nested objects are better served by `--output json`.
- Error responses from `FeanorAPIError` should print `error: <message>` to stderr
  and exit with code 1.
- The `feanor workflows run` command is a stub that prints a "use feanor executions"
  message until Phase 2 dispatch is wired. Do not leave a bare `NotImplementedError`.
