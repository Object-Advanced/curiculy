"""Lesson-plan builder fields on pacing guides and their lessons.

Revision ID: 0007_lesson_plan_builder
Revises: 0006_attendance
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_lesson_plan_builder"
down_revision: Union[str, Sequence[str], None] = "0006_attendance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "curriculum_plans",
        sa.Column(
            "frequency_days",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
    )
    op.add_column(
        "curriculum_plans",
        sa.Column(
            "total_weeks",
            sa.Integer(),
            nullable=False,
            server_default="36",
        ),
    )
    op.add_column(
        "curriculum_plans",
        sa.Column("grading_weights", sa.Text(), nullable=True),
    )
    op.add_column(
        "curriculum_plans",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "curriculum_lessons",
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "curriculum_lessons",
        sa.Column("category", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "curriculum_lessons",
        sa.Column("resources", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("curriculum_lessons", "resources")
    op.drop_column("curriculum_lessons", "category")
    op.drop_column("curriculum_lessons", "notes")
    op.drop_column("curriculum_plans", "is_archived")
    op.drop_column("curriculum_plans", "grading_weights")
    op.drop_column("curriculum_plans", "total_weeks")
    op.drop_column("curriculum_plans", "frequency_days")
