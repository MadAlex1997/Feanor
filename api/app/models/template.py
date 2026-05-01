import enum
import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class TemplateType(str, enum.Enum):
    serverless = "serverless"
    container_job = "container_job"
    distributed = "distributed"


class ExecutionTemplate(TimestampMixin, Base):
    __tablename__ = "execution_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    type: Mapped[TemplateType] = mapped_column(
        SAEnum(TemplateType, name="templatetype"), nullable=False
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
