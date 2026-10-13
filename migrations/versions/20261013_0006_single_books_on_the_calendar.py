"""Single books on the calendar: a curriculum of one item, scheduled from the Library.

``planned_curricula.solo`` marks the one-item curricula the Library's
"Schedule" makes, so the planner's list and the community catalog leave them
out. Curricula without a textbook need no schema change.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('planned_curricula', sa.Column('solo', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('planned_curricula', 'solo')
