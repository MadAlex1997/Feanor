from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    request_id: str


class APIResponse(BaseModel, Generic[T]):
    data: T | None
    error: str | None = None
    meta: Any  # Meta or PaginatedMeta — serialized as-is
