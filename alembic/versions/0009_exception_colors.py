"""Exception color scheme on household settings.

Revision ID: 0009_exception_colors
Revises: 0008_household_settings
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_exception_colors"
down_revision: Union[str, Sequence[str], None] = "0008_household_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "household_settings",
        sa.Column("exception_colors", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("household_settings", "exception_colors")
