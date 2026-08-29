"""Household school-year bounds and default class days.

Revision ID: 0008_household_settings
Revises: 0007_lesson_plan_builder
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_household_settings"
down_revision: Union[str, Sequence[str], None] = "0007_lesson_plan_builder"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "household_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("weekdays", sa.String(length=32), nullable=False, server_default="0,1,2,3,4"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.UniqueConstraint("household_id", name="uq_household_settings_household"),
    )


def downgrade() -> None:
    op.drop_table("household_settings")
