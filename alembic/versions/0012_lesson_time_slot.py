"""Add time_slot to structured pacing-guide lessons.

Revision ID: 0012_lesson_time_slot
Revises: 0011_curriculum_plan_status
Create Date: 2026-08-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_lesson_time_slot"
down_revision: Union[str, Sequence[str], None] = "0011_curriculum_plan_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "curriculum_lessons",
        sa.Column("time_slot", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("curriculum_lessons", "time_slot")
