import uuid

from sqlalchemy import LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Connector(TimestampMixin, Base):
    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    # Plaintext for MVP; encryption is a Phase 6 concern (see task-006 notes).
    config_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    owner: Mapped[str] = mapped_column(String, nullable=False)
