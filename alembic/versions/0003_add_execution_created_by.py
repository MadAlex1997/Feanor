"""Add created_by column to executions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Allow NULL initially so existing rows aren't rejected, then default to ''
    op.add_column(
        "executions",
        sa.Column("created_by", sa.String(), nullable=True),
    )
    op.execute(sa.text("UPDATE executions SET created_by = '' WHERE created_by IS NULL"))
    op.alter_column("executions", "created_by", nullable=False)


def downgrade() -> None:
    op.drop_column("executions", "created_by")
