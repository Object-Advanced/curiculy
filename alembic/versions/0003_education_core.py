"""Core educational data model: subject taxonomy, classifications, assignments.

Adds the taxonomy tables (subject_taxonomies, reporting_categories), the
association that files a catalog resource under them (curriculum_classifications),
and the assignment event tables (assignments, assignment_grades,
assignment_evidence).

Revision ID: 0003_education_core
Revises: 0002_curriculum_catalog
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_education_core"
down_revision: Union[str, Sequence[str], None] = "0002_curriculum_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "subject_taxonomies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["subject_taxonomies.id"],
            name="fk_subject_taxonomies_parent_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("code", name="uq_subject_taxonomies_code"),
        sa.UniqueConstraint("parent_id", "name", name="uq_subject_taxonomy_parent_name"),
    )
    op.create_index(
        "ix_subject_taxonomies_parent_id",
        "subject_taxonomies",
        ["parent_id"],
    )
    op.create_index(
        "ix_subject_taxonomies_parent_order",
        "subject_taxonomies",
        ["parent_id", "sort_order"],
    )

    op.create_table(
        "reporting_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.UniqueConstraint("code", name="uq_reporting_categories_code"),
    )

    op.create_table(
        "curriculum_classifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("curriculum_resource_id", sa.Integer(), nullable=False),
        sa.Column("subject_taxonomy_id", sa.Integer(), nullable=False),
        sa.Column("reporting_category_id", sa.Integer(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["curriculum_resource_id"],
            ["curriculum_resources.id"],
            name="fk_curriculum_classifications_curriculum_resource_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_taxonomy_id"],
            ["subject_taxonomies.id"],
            name="fk_curriculum_classifications_subject_taxonomy_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reporting_category_id"],
            ["reporting_categories.id"],
            name="fk_curriculum_classifications_reporting_category_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "curriculum_resource_id",
            "subject_taxonomy_id",
            "reporting_category_id",
            name="uq_classification_resource_subject_category",
        ),
    )
    op.create_index(
        "ix_curriculum_classifications_curriculum_resource_id",
        "curriculum_classifications",
        ["curriculum_resource_id"],
    )
    op.create_index(
        "ix_curriculum_classifications_subject_taxonomy_id",
        "curriculum_classifications",
        ["subject_taxonomy_id"],
    )
    op.create_index(
        "ix_curriculum_classifications_reporting_category_id",
        "curriculum_classifications",
        ["reporting_category_id"],
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("curriculum_resource_id", sa.Integer(), nullable=True),
        sa.Column("curriculum_unit_id", sa.Integer(), nullable=True),
        sa.Column("subject_taxonomy_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name="fk_assignments_student_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_resource_id"],
            ["curriculum_resources.id"],
            name="fk_assignments_curriculum_resource_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_unit_id"],
            ["curriculum_units.id"],
            name="fk_assignments_curriculum_unit_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_taxonomy_id"],
            ["subject_taxonomies.id"],
            name="fk_assignments_subject_taxonomy_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_assignments_student_id", "assignments", ["student_id"])
    op.create_index(
        "ix_assignments_curriculum_resource_id",
        "assignments",
        ["curriculum_resource_id"],
    )
    op.create_index(
        "ix_assignments_curriculum_unit_id",
        "assignments",
        ["curriculum_unit_id"],
    )
    op.create_index(
        "ix_assignments_subject_taxonomy_id",
        "assignments",
        ["subject_taxonomy_id"],
    )
    op.create_index("ix_assignments_scheduled_date", "assignments", ["scheduled_date"])
    op.create_index(
        "ix_assignments_student_scheduled_date",
        "assignments",
        ["student_id", "scheduled_date"],
    )
    op.create_index("ix_assignments_student_status", "assignments", ["student_id", "status"])

    op.create_table(
        "assignment_grades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("score_type", sa.String(length=32), nullable=False),
        sa.Column("score_value", sa.String(length=64), nullable=False),
        sa.Column("graded_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="fk_assignment_grades_assignment_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("assignment_id", name="uq_assignment_grade_assignment"),
    )

    op.create_table(
        "assignment_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            name="fk_assignment_evidence_assignment_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_assignment_evidence_assignment_id",
        "assignment_evidence",
        ["assignment_id"],
    )


def downgrade() -> None:
    op.drop_table("assignment_evidence")
    op.drop_table("assignment_grades")
    op.drop_table("assignments")
    op.drop_table("curriculum_classifications")
    op.drop_table("reporting_categories")
    op.drop_table("subject_taxonomies")
