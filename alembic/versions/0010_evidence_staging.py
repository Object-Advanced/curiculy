"""Add the unlinked evidence holding table.

Revision ID: 0010_evidence_staging
Revises: 0009_exception_colors
Create Date: 2026-08-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_evidence_staging"
down_revision: Union[str, Sequence[str], None] = "0009_exception_colors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence_staging",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default="chrome_extension",
        ),
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
    )
    op.create_index("ix_evidence_staging_tenant_id", "evidence_staging", ["tenant_id"])
    op.create_index(
        "ix_evidence_staging_captured_at",
        "evidence_staging",
        ["captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_staging_captured_at", table_name="evidence_staging")
    op.drop_index("ix_evidence_staging_tenant_id", table_name="evidence_staging")
    op.drop_table("evidence_staging")
