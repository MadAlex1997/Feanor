"""Add unique constraint on workflows(slug, version).

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_workflows_slug_version",
        "workflows",
        ["slug", "version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_workflows_slug_version", "workflows", type_="unique")
