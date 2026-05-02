---
title: CLI `feanor query` command with --output formats
phase: 3
status: Pending
---

## Description

Implement the `feanor query "SELECT ..."` CLI command. It calls `client.query(sql)`
from the SDK and renders the results in table, JSON, or YAML format. Supports
streaming progress feedback for long-running queries.

## Acceptance criteria

- [ ] `feanor/cli/commands/query.py` — typer command `query`:

      ```
      feanor query "SELECT * FROM postgresql.public.datasets LIMIT 10"
      feanor query "SELECT ..." --catalog postgresql --schema public
      feanor query "SELECT ..." --output json
      feanor query "SELECT ..." --output yaml
      feanor query "SELECT ..." --output table   # default
      feanor query "SELECT ..." --max-rows 500
      feanor query "SELECT ..." --quiet           # suppress row count footer
      ```

- [ ] `--output table` (default): renders results using `rich.table.Table`.
      Column names as headers. Right-align numeric columns.

- [ ] `--output json`: prints `{"columns": [...], "rows": [...], "query_id": "...",
      "elapsed_ms": N}` as compact JSON to stdout. Machine-readable.

- [ ] `--output yaml`: prints the same structure as YAML.

- [ ] `--catalog` and `--schema` flags passed through to `client.query(...)`.

- [ ] `--max-rows` flag (default `10_000`) passed to `client.query(...)`.

- [ ] Footer printed to stderr (not stdout) after a table render:
      `N rows returned in Xms  (query_id: ...)`. Suppressed by `--quiet`.

- [ ] `FeanorQueryError` from the SDK is caught and printed as a formatted error
      message (`rich` panel or plain stderr), then exits with code `1`.

- [ ] Command registered in `feanor/cli/__init__.py` alongside other commands.

- [ ] `--help` output is accurate and complete.

- [ ] Unit tests (mocked `client.query`):
      - Table output renders column headers and a row.
      - JSON output is valid JSON with the right keys.
      - YAML output is valid YAML.
      - `FeanorQueryError` exits with code `1`.
      - `--quiet` suppresses the footer.

## Dependencies

- task-030 (SDK `client.query` method must exist)
- task-018 (CLI command pattern to follow)

## Notes

- `rich` is already available in the feanor package from prior CLI tasks.
  Use `Console(stderr=True)` for the footer and error messages so that only
  result data goes to stdout when piped.
- For `--output table`, handle the case where `rows` is empty: print
  "0 rows returned" rather than an empty table.
- The `query` subcommand is a top-level command (`feanor query ...`), not nested
  under a resource group. This matches the spec in system-prompt.md.
