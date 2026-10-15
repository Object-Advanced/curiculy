"""Attendance suggestions: how each day was marked, and its minutes.

- ``attendance.source``: "suggestion" when the parent confirmed what
  Curiculy suggested (a lesson checked off or an activity logged that day),
  "parent" when they chose it themselves. Every existing row was the parent's.
- ``attendance.minutes``: the day's school time, when the parent sets it
  (hours-mode families); otherwise lessons and activities are added up.
- The "Field trip" status (counts as present) needs no change: statuses are
  stored as text.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'attendance',
        sa.Column('source', sa.String(length=16), server_default='parent', nullable=False),
    )
    op.add_column('attendance', sa.Column('minutes', sa.Integer(), nullable=True))


def downgrade() -> None:
    # The older code doesn't know "Field trip": keep those days as present.
    op.execute("UPDATE attendance SET status = 'Present' WHERE status = 'Field trip'")
    op.drop_column('attendance', 'minutes')
    op.drop_column('attendance', 'source')
