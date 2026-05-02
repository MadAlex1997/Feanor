from __future__ import annotations

from pydantic import BaseModel


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[dict]
    query_id: str
    elapsed_ms: int
