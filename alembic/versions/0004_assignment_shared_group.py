"""Link assignments that are the same shared lesson for several students.

Adds ``assignments.shared_group_uuid`` so a group-scheduled lesson can be found
again when attaching evidence to every student who received it.

Revision ID: 0004_assignment_shared_group
Revises: 0003_education_core
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_assignment_shared_group"
down_revision: Union[str, Sequence[str], None] = "0003_education_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column("shared_group_uuid", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_assignments_shared_group_uuid",
        "assignments",
        ["shared_group_uuid"],
    )


def downgrade() -> None:
    op.drop_index("ix_assignments_shared_group_uuid", table_name="assignments")
    op.drop_column("assignments", "shared_group_uuid")
