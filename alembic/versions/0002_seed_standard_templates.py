"""Seed four standard execution templates.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("""
            INSERT INTO execution_templates (id, name, type, config, created_at, updated_at)
            VALUES
              (gen_random_uuid(), 'serverless_standard', 'serverless',
               '{"max_duration_minutes": 15, "max_memory_mb": 3072, "stateless": true}',
               now(), now()),
              (gen_random_uuid(), 'container_job_standard', 'container_job',
               '{"max_duration_hours": 24, "ephemeral_disk": true}',
               now(), now()),
              (gen_random_uuid(), 'container_job_gpu', 'container_job',
               '{"max_duration_hours": 24, "ephemeral_disk": true, "gpu": true}',
               now(), now()),
              (gen_random_uuid(), 'distributed_spark_medium', 'distributed',
               '{"engine": "spark", "spark_version": "3.x", "auto_scaling": true}',
               now(), now())
        """)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM execution_templates WHERE name IN "
            "('serverless_standard', 'container_job_standard', "
            "'container_job_gpu', 'distributed_spark_medium')"
        )
    )
