import uuid
from typing import Any

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Workflow(TimestampMixin, Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False)
    definition: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    execution_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("execution_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )

    template: Mapped["ExecutionTemplate"] = relationship("ExecutionTemplate")  # type: ignore[name-defined]  # noqa: F821
