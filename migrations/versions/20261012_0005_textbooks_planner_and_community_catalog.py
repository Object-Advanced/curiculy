"""Textbooks, the Curriculum planner, and the community catalog.

The Library's kinds become Book, Textbook, Workbook and Online site: a
textbook carries its own lesson list (each lesson's pages), so the separate
"materials" and per-material lesson pages go (``library_materials``,
``library_lesson_pages``), and any old "curriculum" items with them (there are
no real families yet). Lessons get ``start_page``/``end_page``; items get
``for_parent`` (a teacher's edition) and their link to the catalog.

The Curriculum planner adds ``planned_curricula`` (a subject's textbook plus
what goes with it), ``planned_curriculum_items`` and ``courses`` (a curriculum
scheduled for one child). Lessons on the calendar remember their course,
library item and textbook lesson. All three are family tables.

The community catalog adds shared tables, outside any family's data:
``catalog_entries`` (versioned in ``catalog_entry_versions``),
``catalog_contributions`` with their ``catalog_flags``, and
``community_curricula`` with ``community_curriculum_items``.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from migrations import tenancy

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('catalog_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('title_key', sa.String(length=255), nullable=False),
    sa.Column('author', sa.String(length=255), nullable=True),
    sa.Column('publisher', sa.String(length=255), nullable=True),
    sa.Column('edition', sa.String(length=64), nullable=True),
    sa.Column('isbn', sa.String(length=20), nullable=True),
    sa.Column('subject_code', sa.String(length=32), nullable=True),
    sa.Column('grade', sa.String(length=8), nullable=True),
    sa.Column('total_pages', sa.Integer(), nullable=True),
    sa.Column('chapters_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('lessons_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('cover_url', sa.String(length=1024), nullable=True),
    sa.Column('cover_path', sa.String(length=1024), nullable=True),
    sa.Column('cover_hash', sa.String(length=32), nullable=True),
    sa.Column('current_version', sa.Integer(), nullable=False),
    sa.Column('families_count', sa.Integer(), server_default='1', nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_entries_cover_hash'), 'catalog_entries', ['cover_hash'], unique=False)
    op.create_index(op.f('ix_catalog_entries_isbn'), 'catalog_entries', ['isbn'], unique=False)
    op.create_index(op.f('ix_catalog_entries_kind'), 'catalog_entries', ['kind'], unique=False)
    op.create_index(op.f('ix_catalog_entries_status'), 'catalog_entries', ['status'], unique=False)
    op.create_index(op.f('ix_catalog_entries_title_key'), 'catalog_entries', ['title_key'], unique=False)
    op.create_table('community_curricula',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('subject_code', sa.String(length=32), nullable=True),
    sa.Column('grade', sa.String(length=8), nullable=True),
    sa.Column('days_per_week', sa.Integer(), nullable=True),
    sa.Column('textbook_entry_id', sa.Integer(), nullable=False),
    sa.Column('signature', sa.String(length=1024), nullable=False),
    sa.Column('families_count', sa.Integer(), server_default='1', nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['textbook_entry_id'], ['catalog_entries.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('signature')
    )
    op.create_index(op.f('ix_community_curricula_textbook_entry_id'), 'community_curricula', ['textbook_entry_id'], unique=False)
    op.create_table('catalog_contributions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('item_kind', sa.String(length=16), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('isbn', sa.String(length=20), nullable=True),
    sa.Column('contributor', sa.String(length=64), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=True),
    sa.Column('based_on_version', sa.Integer(), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('data_hash', sa.String(length=64), nullable=False),
    sa.Column('cover_path', sa.String(length=1024), nullable=True),
    sa.Column('cover_hash', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('needs_review', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reviewed_by', sa.String(length=255), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('result_entry_id', sa.Integer(), nullable=True),
    sa.Column('result_curriculum_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['entry_id'], ['catalog_entries.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['result_curriculum_id'], ['community_curricula.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['result_entry_id'], ['catalog_entries.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_contributions_contributor'), 'catalog_contributions', ['contributor'], unique=False)
    op.create_index(op.f('ix_catalog_contributions_data_hash'), 'catalog_contributions', ['data_hash'], unique=False)
    op.create_index(op.f('ix_catalog_contributions_entry_id'), 'catalog_contributions', ['entry_id'], unique=False)
    op.create_index(op.f('ix_catalog_contributions_isbn'), 'catalog_contributions', ['isbn'], unique=False)
    op.create_index(op.f('ix_catalog_contributions_kind'), 'catalog_contributions', ['kind'], unique=False)
    op.create_index(op.f('ix_catalog_contributions_status'), 'catalog_contributions', ['status'], unique=False)
    op.create_index('uq_catalog_contributions_open', 'catalog_contributions', ['contributor', 'kind', 'source_id'], unique=True, postgresql_where=sa.text("status IN ('pending', 'asked')"))
    op.create_table('community_curriculum_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('curriculum_id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['curriculum_id'], ['community_curricula.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['entry_id'], ['catalog_entries.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_community_curriculum_items_curriculum_id'), 'community_curriculum_items', ['curriculum_id'], unique=False)
    op.create_index(op.f('ix_community_curriculum_items_entry_id'), 'community_curriculum_items', ['entry_id'], unique=False)
    op.create_table('catalog_entry_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('data_hash', sa.String(length=64), nullable=False),
    sa.Column('contribution_id', sa.Integer(), nullable=True),
    sa.Column('approved_by', sa.String(length=255), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['contribution_id'], ['catalog_contributions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['entry_id'], ['catalog_entries.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entry_id', 'version', name='uq_catalog_entry_versions_version')
    )
    op.create_index(op.f('ix_catalog_entry_versions_data_hash'), 'catalog_entry_versions', ['data_hash'], unique=False)
    op.create_index(op.f('ix_catalog_entry_versions_entry_id'), 'catalog_entry_versions', ['entry_id'], unique=False)
    op.create_table('catalog_flags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contribution_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=48), nullable=False),
    sa.Column('group', sa.String(length=16), nullable=False),
    sa.Column('level', sa.String(length=8), nullable=False),
    sa.Column('where', sa.String(length=255), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['contribution_id'], ['catalog_contributions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_catalog_flags_contribution_id'), 'catalog_flags', ['contribution_id'], unique=False)
    op.create_table('planned_curricula',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('subject_code', sa.String(length=32), nullable=True),
    sa.Column('grade', sa.String(length=8), nullable=True),
    sa.Column('days_per_week', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('community_curriculum_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['community_curriculum_id'], ['community_curricula.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_planned_curricula_tenant_id'), 'planned_curricula', ['tenant_id'], unique=False)
    op.create_table('planned_curriculum_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('curriculum_id', sa.Integer(), nullable=False),
    sa.Column('library_item_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['curriculum_id'], ['planned_curricula.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['library_item_id'], ['library_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_planned_curriculum_items_curriculum_id'), 'planned_curriculum_items', ['curriculum_id'], unique=False)
    op.create_index(op.f('ix_planned_curriculum_items_library_item_id'), 'planned_curriculum_items', ['library_item_id'], unique=False)
    op.create_index(op.f('ix_planned_curriculum_items_tenant_id'), 'planned_curriculum_items', ['tenant_id'], unique=False)
    op.create_table('courses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('curriculum_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('school_year_id', sa.Integer(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('weekdays', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['curriculum_id'], ['planned_curricula.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['school_year_id'], ['school_years.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_courses_curriculum_id'), 'courses', ['curriculum_id'], unique=False)
    op.create_index(op.f('ix_courses_school_year_id'), 'courses', ['school_year_id'], unique=False)
    op.create_index(op.f('ix_courses_student_id'), 'courses', ['student_id'], unique=False)
    op.create_index(op.f('ix_courses_tenant_id'), 'courses', ['tenant_id'], unique=False)
    # The old "curriculum" kind is now a textbook with its own lesson list.
    op.execute("DELETE FROM library_items WHERE kind = 'curriculum'")
    op.drop_index(op.f('ix_library_lesson_pages_lesson_id'), table_name='library_lesson_pages')
    op.drop_index(op.f('ix_library_lesson_pages_material_id'), table_name='library_lesson_pages')
    op.drop_index(op.f('ix_library_lesson_pages_tenant_id'), table_name='library_lesson_pages')
    op.drop_table('library_lesson_pages')
    op.drop_index(op.f('ix_library_materials_item_id'), table_name='library_materials')
    op.drop_index(op.f('ix_library_materials_tenant_id'), table_name='library_materials')
    op.drop_table('library_materials')
    op.add_column('assignments', sa.Column('course_id', sa.Integer(), nullable=True))
    op.add_column('assignments', sa.Column('library_item_id', sa.Integer(), nullable=True))
    op.add_column('assignments', sa.Column('library_lesson_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_assignments_course_id'), 'assignments', ['course_id'], unique=False)
    op.create_index(op.f('ix_assignments_library_item_id'), 'assignments', ['library_item_id'], unique=False)
    op.create_foreign_key('assignments_course_id_fkey', 'assignments', 'courses', ['course_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('assignments_library_lesson_id_fkey', 'assignments', 'library_lessons', ['library_lesson_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('assignments_library_item_id_fkey', 'assignments', 'library_items', ['library_item_id'], ['id'], ondelete='SET NULL')
    op.add_column('library_items', sa.Column('for_parent', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('library_items', sa.Column('catalog_entry_id', sa.Integer(), nullable=True))
    op.add_column('library_items', sa.Column('catalog_version', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_library_items_catalog_entry_id'), 'library_items', ['catalog_entry_id'], unique=False)
    op.create_foreign_key('library_items_catalog_entry_id_fkey', 'library_items', 'catalog_entries', ['catalog_entry_id'], ['id'], ondelete='SET NULL')
    op.add_column('library_lessons', sa.Column('start_page', sa.Integer(), nullable=True))
    op.add_column('library_lessons', sa.Column('end_page', sa.Integer(), nullable=True))
    for table in ("planned_curricula", "planned_curriculum_items", "courses"):
        tenancy.protect_family_table(table)
    tenancy.add_family_reference("planned_curriculum_items", ["curriculum_id"], "planned_curricula", ondelete="CASCADE")
    tenancy.add_family_reference("planned_curriculum_items", ["library_item_id"], "library_items", ondelete="CASCADE")
    tenancy.add_family_reference("courses", ["curriculum_id"], "planned_curricula", ondelete="CASCADE")
    tenancy.add_family_reference("courses", ["student_id"], "students", ondelete="CASCADE")
    tenancy.add_family_reference("courses", ["school_year_id"], "school_years", ondelete="SET NULL")
    tenancy.add_family_reference("assignments", ["course_id"], "courses", ondelete="SET NULL")
    tenancy.add_family_reference("assignments", ["library_item_id"], "library_items", ondelete="SET NULL")
    tenancy.add_family_reference("assignments", ["library_lesson_id"], "library_lessons", ondelete="SET NULL")


def downgrade() -> None:
    op.drop_column('library_lessons', 'end_page')
    op.drop_column('library_lessons', 'start_page')
    op.drop_constraint('library_items_catalog_entry_id_fkey', 'library_items', type_='foreignkey')
    op.drop_index(op.f('ix_library_items_catalog_entry_id'), table_name='library_items')
    op.drop_column('library_items', 'catalog_version')
    op.drop_column('library_items', 'catalog_entry_id')
    op.drop_column('library_items', 'for_parent')
    # Dropping the columns also drops their family-matching (tenant) references.
    op.drop_constraint('assignments_library_item_id_fkey', 'assignments', type_='foreignkey')
    op.drop_constraint('assignments_library_lesson_id_fkey', 'assignments', type_='foreignkey')
    op.drop_constraint('assignments_course_id_fkey', 'assignments', type_='foreignkey')
    op.drop_index(op.f('ix_assignments_library_item_id'), table_name='assignments')
    op.drop_index(op.f('ix_assignments_course_id'), table_name='assignments')
    op.drop_column('assignments', 'library_lesson_id')
    op.drop_column('assignments', 'library_item_id')
    op.drop_column('assignments', 'course_id')
    op.create_table('library_materials',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('isbn', sa.String(length=20), nullable=True),
    sa.Column('pages', sa.Integer(), nullable=True),
    sa.Column('audience', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['library_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_library_materials_tenant_id'), 'library_materials', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_library_materials_item_id'), 'library_materials', ['item_id'], unique=False)
    op.create_table('library_lesson_pages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lesson_id', sa.Integer(), nullable=False),
    sa.Column('material_id', sa.Integer(), nullable=False),
    sa.Column('start_page', sa.Integer(), nullable=False),
    sa.Column('end_page', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('tenant_id', sa.String(length=64), server_default=sa.text('curiculy_current_tenant()'), nullable=False),
    sa.ForeignKeyConstraint(['lesson_id'], ['library_lessons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['material_id'], ['library_materials.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_library_lesson_pages_tenant_id'), 'library_lesson_pages', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_library_lesson_pages_material_id'), 'library_lesson_pages', ['material_id'], unique=False)
    op.create_index(op.f('ix_library_lesson_pages_lesson_id'), 'library_lesson_pages', ['lesson_id'], unique=False)
    for table in ("library_materials", "library_lesson_pages"):
        tenancy.protect_family_table(table)
    tenancy.add_family_reference("library_materials", ["item_id"], "library_items", ondelete="CASCADE")
    tenancy.add_family_reference("library_lesson_pages", ["lesson_id"], "library_lessons", ondelete="CASCADE")
    tenancy.add_family_reference("library_lesson_pages", ["material_id"], "library_materials", ondelete="CASCADE")
    op.drop_index(op.f('ix_courses_tenant_id'), table_name='courses')
    op.drop_index(op.f('ix_courses_student_id'), table_name='courses')
    op.drop_index(op.f('ix_courses_school_year_id'), table_name='courses')
    op.drop_index(op.f('ix_courses_curriculum_id'), table_name='courses')
    op.drop_table('courses')
    op.drop_index(op.f('ix_planned_curriculum_items_tenant_id'), table_name='planned_curriculum_items')
    op.drop_index(op.f('ix_planned_curriculum_items_library_item_id'), table_name='planned_curriculum_items')
    op.drop_index(op.f('ix_planned_curriculum_items_curriculum_id'), table_name='planned_curriculum_items')
    op.drop_table('planned_curriculum_items')
    op.drop_index(op.f('ix_planned_curricula_tenant_id'), table_name='planned_curricula')
    op.drop_table('planned_curricula')
    op.drop_index(op.f('ix_catalog_flags_contribution_id'), table_name='catalog_flags')
    op.drop_table('catalog_flags')
    op.drop_index(op.f('ix_catalog_entry_versions_entry_id'), table_name='catalog_entry_versions')
    op.drop_index(op.f('ix_catalog_entry_versions_data_hash'), table_name='catalog_entry_versions')
    op.drop_table('catalog_entry_versions')
    op.drop_index(op.f('ix_community_curriculum_items_entry_id'), table_name='community_curriculum_items')
    op.drop_index(op.f('ix_community_curriculum_items_curriculum_id'), table_name='community_curriculum_items')
    op.drop_table('community_curriculum_items')
    op.drop_index('uq_catalog_contributions_open', table_name='catalog_contributions', postgresql_where=sa.text("status IN ('pending', 'asked')"))
    op.drop_index(op.f('ix_catalog_contributions_status'), table_name='catalog_contributions')
    op.drop_index(op.f('ix_catalog_contributions_kind'), table_name='catalog_contributions')
    op.drop_index(op.f('ix_catalog_contributions_isbn'), table_name='catalog_contributions')
    op.drop_index(op.f('ix_catalog_contributions_entry_id'), table_name='catalog_contributions')
    op.drop_index(op.f('ix_catalog_contributions_data_hash'), table_name='catalog_contributions')
    op.drop_index(op.f('ix_catalog_contributions_contributor'), table_name='catalog_contributions')
    op.drop_table('catalog_contributions')
    op.drop_index(op.f('ix_community_curricula_textbook_entry_id'), table_name='community_curricula')
    op.drop_table('community_curricula')
    op.drop_index(op.f('ix_catalog_entries_title_key'), table_name='catalog_entries')
    op.drop_index(op.f('ix_catalog_entries_status'), table_name='catalog_entries')
    op.drop_index(op.f('ix_catalog_entries_kind'), table_name='catalog_entries')
    op.drop_index(op.f('ix_catalog_entries_isbn'), table_name='catalog_entries')
    op.drop_index(op.f('ix_catalog_entries_cover_hash'), table_name='catalog_entries')
    op.drop_table('catalog_entries')
