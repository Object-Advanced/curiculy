"""No AI for children: "Stuck?" no longer counts asking the AI for answers.

The nudge is now built from the lesson itself (its book, pages and the
parent's note), and the child types nothing, so
``homework_help_sessions.push_count`` (how often a child pushed the AI for an
answer) has nothing to count.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('homework_help_sessions', 'push_count')


def downgrade() -> None:
    op.add_column('homework_help_sessions', sa.Column('push_count', sa.Integer(), server_default='0', nullable=False))
