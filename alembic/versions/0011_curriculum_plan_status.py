"""Add processing status to structured pacing guides.

Revision ID: 0011_curriculum_plan_status
Revises: 0010_evidence_staging
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_curriculum_plan_status"
down_revision: Union[str, Sequence[str], None] = "0010_evidence_staging"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "curriculum_plans",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ready",
        ),
    )


def downgrade() -> None:
    op.drop_column("curriculum_plans", "status")
