---
title: "CLI: feanor workflows run, executions logs --follow, executions cancel"
phase: 2
status: Pending
---

## Description

Wire up the three Phase 2 CLI commands that let users interact with the execution
pipeline from the terminal. These commands call the SDK methods added in task-025
and use the existing `render()` output helper.

## Acceptance criteria

- [ ] `feanor/cli/commands/workflows.py` — extend existing module:
      - `feanor workflows run <workflow> [--input key=value ...] [--wait] [--timeout N] [--output FORMAT]`
        - `workflow`: a `slug:version` string or UUID.
        - `--input key=value`: repeatable flag; parsed as `key=value` pairs into a
          dict. Values are plain strings. Raise `typer.BadParameter` if a value
          cannot be parsed as `key=value`.
        - `--wait`: if set, passes `wait=True` and `--timeout` to `executions.submit()`.
          Prints "Waiting for execution to complete..." before blocking.
        - `--timeout N`: integer seconds (default 60, max 300). Passed to
          `submit(timeout=N)`. Only valid with `--wait`; emit a warning if used
          without `--wait`.
        - On success: renders the `Execution` object using `render()` in the
          requested output format (default table).
        - On `FeanorAPIError(408, ...)`: prints "Execution timed out. Use
          `feanor executions get <id>` to check status." and exits with code 1.

- [ ] `feanor/cli/commands/executions.py` — extend existing module:
      - `feanor executions cancel <execution_id> [--output FORMAT]`
        - Calls `client.executions.cancel(execution_id)`.
        - Prints "Execution cancelled." then renders the updated `Execution`.
        - On `FeanorAPIError(409, ...)`: prints the error message and exits 1.
        - On `FeanorAPIError(404, ...)`: prints "Execution not found." and exits 1.

      - `feanor executions logs <execution_id> [--tail N] [--follow] [--interval S]`
        - `--tail N`: integer; if set, pass `tail=N` to `client.executions.logs()`.
        - `--follow`: poll-and-print mode. Prints new lines as they appear.
          Implementation: loop calling `client.executions.logs(tail=N)` every
          `--interval` seconds (default 2) until the execution reaches a terminal
          status, then print remaining logs and exit. Uses
          `client.executions.get(execution_id)` to check status after each poll.
        - Without `--follow`: calls `logs()` once and prints. If result is `None`,
          prints "No logs available yet." to stderr and exits 0.
        - `--interval S`: float seconds between polls when `--follow` is active
          (default 2.0, min 1.0).

- [ ] `feanor/cli/commands/executions.py` — table columns for `Execution`:
      `["id", "workflow_id", "status", "created_at", "started_at", "ended_at"]`
      (reuse or extend the column list already used in `executions list`).

- [ ] `feanor/cli/commands/workflows.py` — table columns for the post-run
      `Execution` response: same column list as executions.

- [ ] Unit tests (`tests/unit/test_cli_workflows.py`, `tests/unit/test_cli_executions.py`):
      - `workflows run slug:version --input a=1 --input b=2` calls
        `submit(workflow="slug:version", inputs={"a": "1", "b": "2"}, wait=False)`.
      - `workflows run ... --wait --timeout 30` calls `submit(wait=True, timeout=30)`.
      - 408 error prints timeout message and exits 1.
      - `executions cancel <id>` calls `cancel(id)` and prints "Execution cancelled."
      - `executions cancel <id>` on 409 prints error message and exits 1.
      - `executions logs <id>` prints log text.
      - `executions logs <id>` on 204 prints "No logs available yet."
      - `executions logs <id> --tail 10` passes `tail=10` to SDK.
      - `executions logs <id> --follow` polls until terminal status then exits.

## Dependencies

- task-025 (SDK `submit()`, `cancel()`, `logs()` methods)
- task-018 (existing CLI command structure to extend)

## Notes

- The `--follow` implementation is a simple poll-print loop, not SSE. The task
  spec intentionally defers real streaming (SSE) to task-028 (Phase 3). For Phase
  2, calling `logs(tail=N)` in a loop is sufficient.
- `--follow` should clear seen lines to avoid re-printing. Track the line count
  from the previous poll; on each iteration, print only lines after the previous
  count. This avoids full text diffs.
- `--input key=value` parsing must handle values that contain `=` (e.g.
  `--input url=https://example.com?a=1`). Split only on the first `=`.
- For `--follow`, when the execution reaches a terminal state, do one final log
  fetch (without tail) to ensure all output is printed, then exit 0 (or 1 if
  status is `failed`).
- Exit codes: 0 for success and cancelled, 1 for failed and timeout, 2 for
  not-found or permission errors. This aligns with standard CLI conventions.
