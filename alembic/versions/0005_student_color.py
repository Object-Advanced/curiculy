"""Add a calendar color to each student.

Revision ID: 0005_student_color
Revises: 0004_assignment_shared_group
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_student_color"
down_revision: Union[str, Sequence[str], None] = "0004_assignment_shared_group"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "color_hex",
            sa.String(length=7),
            nullable=False,
            server_default="#356b46",
        ),
    )


def downgrade() -> None:
    op.drop_column("students", "color_hex")
