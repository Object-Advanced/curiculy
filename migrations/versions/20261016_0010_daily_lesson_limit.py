"""The move engine: a daily lesson limit per family.

``households.daily_lesson_limit``: the most lessons a child should have in a
day. Moves warn above it, and the catch-up sheet's "double up" stays under
it. Empty means no limit is set.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('households', sa.Column('daily_lesson_limit', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('households', 'daily_lesson_limit')
