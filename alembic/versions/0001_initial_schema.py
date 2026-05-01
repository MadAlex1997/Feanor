"""Initial schema — all Phase 0 tables.

Revision ID: 0001
Revises:
Create Date: 2026-05-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # execution_templates must precede workflows (FK target)
    op.create_table(
        "execution_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "type",
            # Let SQLAlchemy own the CREATE TYPE for templatetype.
            postgresql.ENUM(
                "serverless",
                "container_job",
                "distributed",
                name="templatetype",
            ),
            nullable=False,
        ),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_execution_templates_name"),
    )

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source_ref", sa.String(), nullable=False),
        sa.Column("schema_hints", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("lineage_refs", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=True),
        sa.Column(
            "execution_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("execution_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            # Let SQLAlchemy own the CREATE TYPE for executionstatus.
            postgresql.ENUM(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="executionstatus",
            ),
            nullable=False,
        ),
        sa.Column("inputs", postgresql.JSONB(), nullable=True),
        sa.Column("result_ref", sa.String(), nullable=True),
        sa.Column("log_ref", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "connectors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("config_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "system_state",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("system_state")
    op.drop_table("connectors")
    op.drop_table("executions")
    op.drop_table("workflows")
    op.drop_table("datasets")
    op.drop_table("execution_templates")
    op.execute(sa.text("DROP TYPE IF EXISTS executionstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS templatetype"))
