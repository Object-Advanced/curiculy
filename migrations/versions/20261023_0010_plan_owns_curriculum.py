"""A pacing guide remembers the curriculum it enrolls against.

Applying used to reuse any ``curricula`` row with the same title, so two
guides named "Math" shared one enrollment. The guide now stores that row's
id. Existing guides are left null; the next apply creates a fresh row and
does not search by title.

The family-matching foreign key is required: both tables are family tables,
and startup refuses a reference that can point at another family's row.
Deleting the curriculum clears the guide's id and leaves its lessons.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from migrations import tenancy

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "curriculum_plans",
        sa.Column("curriculum_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_curriculum_plans_curriculum_id"),
        "curriculum_plans",
        ["curriculum_id"],
        unique=False,
    )
    op.create_foreign_key(
        "curriculum_plans_curriculum_id_fkey",
        "curriculum_plans",
        "curricula",
        ["curriculum_id"],
        ["id"],
        ondelete="SET NULL",
    )
    tenancy.add_family_reference(
        "curriculum_plans", ["curriculum_id"], "curricula", ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tenant_curriculum_plans_curriculum_id",
        "curriculum_plans",
        type_="foreignkey",
    )
    op.drop_constraint(
        "curriculum_plans_curriculum_id_fkey",
        "curriculum_plans",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_curriculum_plans_curriculum_id"), table_name="curriculum_plans"
    )
    op.drop_column("curriculum_plans", "curriculum_id")
