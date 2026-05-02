"""Federated query resource — executes SQL against Trino via HTTP API."""
from __future__ import annotations

import time
from typing import Any

import httpx

from feanor.config import Profile
from feanor.exceptions import FeanorQueryError
from feanor.models.query import QueryResult

_DEFAULT_MAX_ROWS = 10_000


class QueryResource:
    """Executes SQL against Trino and returns typed results.

    Uses Trino's HTTP statement API directly (POST /v1/statement + nextUri paging).
    """

    def __init__(self, profile: Profile) -> None:
        self._trino_url = profile.trino_url
        self._token = profile.token

    async def query(
        self,
        sql: str,
        *,
        catalog: str | None = None,
        schema: str | None = None,
        max_rows: int = _DEFAULT_MAX_ROWS,
    ) -> QueryResult:
        headers: dict[str, str] = {"Content-Type": "text/plain"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            # Extract username from token for Trino query history.
            # Best-effort — fall back to "feanor-sdk" if decoding fails.
            headers["X-Trino-User"] = _extract_username(self._token)
        else:
            headers["X-Trino-User"] = "feanor-sdk"

        if catalog:
            headers["X-Trino-Catalog"] = catalog
        if schema:
            headers["X-Trino-Schema"] = schema

        start_ms = int(time.monotonic() * 1000)

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Submit query.
            resp = await client.post(
                f"{self._trino_url}/v1/statement",
                content=sql.encode(),
                headers=headers,
            )
            if not resp.is_success:
                raise FeanorQueryError(
                    f"Trino rejected query (HTTP {resp.status_code}): {resp.text}",
                )

            payload = resp.json()
            _check_error(payload)

            columns: list[str] = []
            all_rows: list[list[Any]] = []

            # Collect columns from first response.
            if "columns" in payload:
                columns = [c["name"] for c in payload["columns"]]

            if "data" in payload:
                all_rows.extend(payload["data"])

            # Follow nextUri links until complete.
            next_uri: str | None = payload.get("nextUri")
            while next_uri:
                if len(all_rows) > max_rows:
                    # Cancel the query and raise.
                    try:
                        await client.delete(next_uri, headers=headers)
                    except Exception:
                        pass
                    raise FeanorQueryError(
                        f"Query returned more than {max_rows} rows; "
                        "use max_rows= to increase the limit or add a LIMIT clause",
                    )

                resp = await client.get(next_uri, headers=headers)
                if not resp.is_success:
                    raise FeanorQueryError(
                        f"Trino paging error (HTTP {resp.status_code}): {resp.text}",
                    )

                payload = resp.json()
                _check_error(payload)

                if "columns" in payload and not columns:
                    columns = [c["name"] for c in payload["columns"]]

                if "data" in payload:
                    all_rows.extend(payload["data"])

                next_uri = payload.get("nextUri")

        elapsed_ms = int(time.monotonic() * 1000) - start_ms
        query_id: str = payload.get("id", "")

        rows = [dict(zip(columns, row)) for row in all_rows]
        return QueryResult(columns=columns, rows=rows, query_id=query_id, elapsed_ms=elapsed_ms)


def _check_error(payload: dict[str, Any]) -> None:
    """Raise FeanorQueryError if the Trino response contains an error."""
    if "error" in payload:
        err = payload["error"]
        raise FeanorQueryError(
            message=err.get("message", "unknown Trino error"),
            error_name=err.get("errorName"),
        )


def _extract_username(token: str) -> str:
    """Best-effort extraction of preferred_username from a JWT payload."""
    try:
        import base64
        import json

        parts = token.split(".")
        if len(parts) != 3:
            return "feanor-sdk"
        # Add padding so base64 doesn't choke on non-padded tokens.
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        return claims.get("preferred_username") or claims.get("sub") or "feanor-sdk"
    except Exception:
        return "feanor-sdk"
