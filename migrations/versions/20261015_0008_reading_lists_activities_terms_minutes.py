"""Reading lists, activities, school-year terms and lesson minutes.

- ``reading_list_entries``: each child's books for a school year (up next,
  reading, finished), tracked by the parent or scheduled.
- ``activities`` with ``activity_students`` and ``activity_evidence``: subjects
  without a curriculum (PE, music, art, safety), with minutes, photos and a link.
- ``school_year_terms``: quarters by default; every existing year gets four
  even quarters here. ``school_years.terms_by_parent`` marks years whose terms
  the parent set.
- ``assignments.minutes``, ``courses.default_minutes`` and
  ``households.count_by`` ("days" or "hours"): what hours-mode families count.

All new tables are family tables (protected and family-matched).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-15
"""

from collections.abc import Sequence
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations import tenancy

revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('activities',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('on_date', sa.Date(), nullable=False),
    sa.Column('minutes', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('link_url', sa.String(length=1024), nullable=True),
    sa.Column('subject_codes', postgresql.ARRAY(sa.String(length=32)), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activities_on_date'), 'activities', ['on_date'], unique=False)
    op.create_index(op.f('ix_activities_tenant_id'), 'activities', ['tenant_id'], unique=False)
    op.create_table('activity_evidence',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('file_path', sa.String(length=1024), nullable=False),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activity_evidence_activity_id'), 'activity_evidence', ['activity_id'], unique=False)
    op.create_index(op.f('ix_activity_evidence_tenant_id'), 'activity_evidence', ['tenant_id'], unique=False)
    op.create_table('activity_students',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activity_id', 'student_id', name='uq_activity_students_child')
    )
    op.create_index(op.f('ix_activity_students_activity_id'), 'activity_students', ['activity_id'], unique=False)
    op.create_index(op.f('ix_activity_students_student_id'), 'activity_students', ['student_id'], unique=False)
    op.create_index(op.f('ix_activity_students_tenant_id'), 'activity_students', ['tenant_id'], unique=False)
    op.create_table('reading_list_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('library_item_id', sa.Integer(), nullable=False),
    sa.Column('school_year_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('started_on', sa.Date(), nullable=True),
    sa.Column('finished_on', sa.Date(), nullable=True),
    sa.Column('counts_toward', sa.String(length=32), nullable=True),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['library_item_id'], ['library_items.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('student_id', 'library_item_id', 'school_year_id', name='uq_reading_list_entries_book', postgresql_nulls_not_distinct=True)
    )
    op.create_index(op.f('ix_reading_list_entries_library_item_id'), 'reading_list_entries', ['library_item_id'], unique=False)
    op.create_index(op.f('ix_reading_list_entries_school_year_id'), 'reading_list_entries', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_reading_list_entries_student_id'), 'reading_list_entries', ['student_id'], unique=False)
    op.create_index(op.f('ix_reading_list_entries_tenant_id'), 'reading_list_entries', ['tenant_id'], unique=False)
    op.create_table('school_year_terms',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('school_year_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_school_year_terms_school_year_id'), 'school_year_terms', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_school_year_terms_tenant_id'), 'school_year_terms', ['tenant_id'], unique=False)
    op.add_column('assignments', sa.Column('minutes', sa.Integer(), nullable=True))
    op.add_column('courses', sa.Column('default_minutes', sa.Integer(), nullable=True))
    op.add_column('households', sa.Column('count_by', sa.String(length=8), server_default='days', nullable=False))
    op.add_column('school_years', sa.Column('terms_by_parent', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    for table in ("activities", "activity_evidence", "activity_students", "reading_list_entries", "school_year_terms"):
        tenancy.protect_family_table(table)
    tenancy.add_family_reference("activity_evidence", ["activity_id"], "activities", ondelete="CASCADE")
    tenancy.add_family_reference("activity_students", ["activity_id"], "activities", ondelete="CASCADE")
    tenancy.add_family_reference("activity_students", ["student_id"], "students", ondelete="CASCADE")
    tenancy.add_family_reference("reading_list_entries", ["student_id"], "students", ondelete="CASCADE")
    tenancy.add_family_reference("reading_list_entries", ["library_item_id"], "library_items", ondelete="CASCADE")
    tenancy.add_family_reference("reading_list_entries", ["school_year_id"], "school_years", ondelete="SET NULL")
    tenancy.add_family_reference("school_year_terms", ["school_year_id"], "school_years", ondelete="CASCADE")

    # Every existing school year gets four even quarters (as new years will).
    bind = op.get_bind()
    years = bind.execute(sa.text("SELECT id, tenant_id, start_date, end_date FROM school_years")).all()
    for year in years:
        for position, (name, first, last) in enumerate(_quarters(year.start_date, year.end_date)):
            bind.execute(
                sa.text(
                    "INSERT INTO school_year_terms (tenant_id, school_year_id, position, name, start_date, end_date) "
                    "VALUES (:tenant, :year, :position, :name, :first, :last)"
                ),
                {"tenant": year.tenant_id, "year": year.id, "position": position, "name": name,
                 "first": first, "last": last},
            )


def _quarters(start: date, end: date) -> list[tuple[str, date, date]]:
    """Frozen copy of app.services.terms.even_quarters (2026-10-15)."""
    days = (end - start).days + 1
    if days < 4:
        return [("Quarter 1", start, end)]
    cuts = [start + timedelta(days=round(days * k / 4)) for k in range(5)]
    return [(f"Quarter {k + 1}", cuts[k], cuts[k + 1] - timedelta(days=1)) for k in range(4)]


def downgrade() -> None:
    op.drop_column('school_years', 'terms_by_parent')
    op.drop_column('households', 'count_by')
    op.drop_column('courses', 'default_minutes')
    op.drop_column('assignments', 'minutes')
    op.drop_index(op.f('ix_school_year_terms_tenant_id'), table_name='school_year_terms')
    op.drop_index(op.f('ix_school_year_terms_school_year_id'), table_name='school_year_terms')
    op.drop_table('school_year_terms')
    op.drop_index(op.f('ix_reading_list_entries_tenant_id'), table_name='reading_list_entries')
    op.drop_index(op.f('ix_reading_list_entries_student_id'), table_name='reading_list_entries')
    op.drop_index(op.f('ix_reading_list_entries_school_year_id'), table_name='reading_list_entries')
    op.drop_index(op.f('ix_reading_list_entries_library_item_id'), table_name='reading_list_entries')
    op.drop_table('reading_list_entries')
    op.drop_index(op.f('ix_activity_students_tenant_id'), table_name='activity_students')
    op.drop_index(op.f('ix_activity_students_student_id'), table_name='activity_students')
    op.drop_index(op.f('ix_activity_students_activity_id'), table_name='activity_students')
    op.drop_table('activity_students')
    op.drop_index(op.f('ix_activity_evidence_tenant_id'), table_name='activity_evidence')
    op.drop_index(op.f('ix_activity_evidence_activity_id'), table_name='activity_evidence')
    op.drop_table('activity_evidence')
    op.drop_index(op.f('ix_activities_tenant_id'), table_name='activities')
    op.drop_index(op.f('ix_activities_on_date'), table_name='activities')
    op.drop_table('activities')
