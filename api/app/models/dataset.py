import uuid
from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    source_ref: Mapped[str] = mapped_column(String, nullable=False)
    schema_hints: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    lineage_refs: Mapped[list[Any] | None] = mapped_column(
        JSONB, nullable=True, default=list
    )
