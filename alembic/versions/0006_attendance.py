"""Add the daily attendance table.

Revision ID: 0006_attendance
Revises: 0005_student_color
Create Date: 2026-08-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_attendance"
down_revision: Union[str, Sequence[str], None] = "0005_student_color"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_attendance_student_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("student_id", "date", name="uq_attendance_student_date"),
    )
    op.create_index("ix_attendance_student_id", "attendance", ["student_id"])
    op.create_index("ix_attendance_date", "attendance", ["date"])
    op.create_index(
        "ix_attendance_student_date",
        "attendance",
        ["student_id", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_attendance_student_date", table_name="attendance")
    op.drop_index("ix_attendance_date", table_name="attendance")
    op.drop_index("ix_attendance_student_id", table_name="attendance")
    op.drop_table("attendance")
