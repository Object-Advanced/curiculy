"""Curriculum catalog: publishers, authors, works, editions, units, page mappings.

Also normalizes the free-text curricula.publisher column into the publishers
table and replaces curriculum_structures with curriculum_units.

Revision ID: 0002_curriculum_catalog
Revises: 0001_initial
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_curriculum_catalog"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
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
        "publishers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("name", name="uq_publishers_name"),
    )

    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_name", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "works",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.String(length=255), nullable=True),
        sa.Column("publisher_id", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["publishers.id"],
            name="fk_works_publisher_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_works_publisher_id", "works", ["publisher_id"])

    op.create_table(
        "work_authors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["works.id"],
            name="fk_work_authors_work_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["authors.id"],
            name="fk_work_authors_author_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("work_id", "author_id", "role", name="uq_work_author_role"),
    )
    op.create_index("ix_work_authors_work_id", "work_authors", ["work_id"])
    op.create_index("ix_work_authors_author_id", "work_authors", ["author_id"])

    op.create_table(
        "book_editions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_id", sa.Integer(), nullable=False),
        sa.Column("publisher_id", sa.Integer(), nullable=True),
        sa.Column("edition_label", sa.String(length=128), nullable=True),
        sa.Column("isbn10", sa.String(length=16), nullable=True),
        sa.Column("isbn13", sa.String(length=20), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("printing", sa.String(length=64), nullable=True),
        sa.Column("book_format", sa.String(length=32), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("page_offset", sa.Integer(), nullable=True),
        sa.Column("cover_image_path", sa.String(length=1024), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["works.id"],
            name="fk_book_editions_work_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"],
            ["publishers.id"],
            name="fk_book_editions_publisher_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("isbn13", name="uq_book_editions_isbn13"),
    )
    op.create_index("ix_book_editions_work_id", "book_editions", ["work_id"])
    op.create_index("ix_book_editions_publisher_id", "book_editions", ["publisher_id"])
    op.create_index("ix_book_editions_isbn10", "book_editions", ["isbn10"])
    op.create_index("ix_book_editions_barcode", "book_editions", ["barcode"])

    op.create_table(
        "curriculum_editions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("curriculum_id", sa.Integer(), nullable=False),
        sa.Column("edition_label", sa.String(length=128), nullable=False),
        sa.Column("copyright_year", sa.Integer(), nullable=True),
        sa.Column("grade_level", sa.String(length=64), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["curriculum_id"],
            ["curricula.id"],
            name="fk_curriculum_editions_curriculum_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "curriculum_id",
            "edition_label",
            name="uq_curriculum_edition_label",
        ),
    )
    op.create_index(
        "ix_curriculum_editions_curriculum_id",
        "curriculum_editions",
        ["curriculum_id"],
    )

    op.create_table(
        "curriculum_resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("curriculum_edition_id", sa.Integer(), nullable=False),
        sa.Column("book_edition_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_consumable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["curriculum_edition_id"],
            ["curriculum_editions.id"],
            name="fk_curriculum_resources_curriculum_edition_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["book_edition_id"],
            ["book_editions.id"],
            name="fk_curriculum_resources_book_edition_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_curriculum_resources_curriculum_edition_id",
        "curriculum_resources",
        ["curriculum_edition_id"],
    )
    op.create_index(
        "ix_curriculum_resources_book_edition_id",
        "curriculum_resources",
        ["book_edition_id"],
    )

    op.create_table(
        "curriculum_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("curriculum_edition_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("estimated_sessions", sa.Integer(), nullable=True),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["curriculum_edition_id"],
            ["curriculum_editions.id"],
            name="fk_curriculum_units_curriculum_edition_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["curriculum_units.id"],
            name="fk_curriculum_units_parent_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_curriculum_units_curriculum_edition_id",
        "curriculum_units",
        ["curriculum_edition_id"],
    )
    op.create_index("ix_curriculum_units_parent_id", "curriculum_units", ["parent_id"])
    op.create_index(
        "ix_curriculum_units_edition_parent_order",
        "curriculum_units",
        ["curriculum_edition_id", "parent_id", "sort_order"],
    )

    op.create_table(
        "curriculum_page_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("curriculum_unit_id", sa.Integer(), nullable=False),
        sa.Column("curriculum_resource_id", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("printed_page_start", sa.String(length=32), nullable=True),
        sa.Column("printed_page_end", sa.String(length=32), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["curriculum_unit_id"],
            ["curriculum_units.id"],
            name="fk_curriculum_page_mappings_curriculum_unit_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_resource_id"],
            ["curriculum_resources.id"],
            name="fk_curriculum_page_mappings_curriculum_resource_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "curriculum_unit_id",
            "curriculum_resource_id",
            "page_start",
            name="uq_page_mapping_unit_resource_start",
        ),
    )
    op.create_index(
        "ix_curriculum_page_mappings_curriculum_unit_id",
        "curriculum_page_mappings",
        ["curriculum_unit_id"],
    )
    op.create_index(
        "ix_curriculum_page_mappings_curriculum_resource_id",
        "curriculum_page_mappings",
        ["curriculum_resource_id"],
    )

    op.execute(
        """
        INSERT INTO publishers (name, created_at, updated_at)
        SELECT DISTINCT TRIM(publisher), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM curricula
        WHERE publisher IS NOT NULL AND TRIM(publisher) <> ''
        """
    )

    with op.batch_alter_table("curricula") as batch:
        batch.add_column(sa.Column("publisher_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE curricula
        SET publisher_id = (
            SELECT p.id FROM publishers p WHERE p.name = TRIM(curricula.publisher)
        )
        WHERE publisher IS NOT NULL AND TRIM(publisher) <> ''
        """
    )

    op.drop_index("ix_curricula_isbn", table_name="curricula")
    op.drop_index("ix_curricula_barcode", table_name="curricula")

    with op.batch_alter_table("curricula") as batch:
        batch.drop_column("publisher")
        batch.drop_column("isbn")
        batch.drop_column("barcode")
        batch.create_foreign_key(
            "fk_curricula_publisher_id",
            "publishers",
            ["publisher_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index("ix_curricula_publisher_id", "curricula", ["publisher_id"])

    with op.batch_alter_table("scheduled_work") as batch:
        batch.drop_column("structure_id")
        batch.add_column(sa.Column("unit_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_scheduled_work_unit_id",
            "curriculum_units",
            ["unit_id"],
            ["id"],
        )

    op.drop_table("curriculum_structures")


def downgrade() -> None:
    op.create_table(
        "curriculum_structures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("curriculum_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["curriculum_id"], ["curricula.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["curriculum_structures.id"]),
    )

    with op.batch_alter_table("scheduled_work") as batch:
        batch.drop_column("unit_id")
        batch.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_scheduled_work_structure_id",
            "curriculum_structures",
            ["structure_id"],
            ["id"],
        )

    op.drop_index("ix_curricula_publisher_id", table_name="curricula")

    with op.batch_alter_table("curricula") as batch:
        batch.add_column(sa.Column("publisher", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("isbn", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("barcode", sa.String(length=64), nullable=True))

    op.execute(
        """
        UPDATE curricula
        SET publisher = (
            SELECT p.name FROM publishers p WHERE p.id = curricula.publisher_id
        )
        WHERE publisher_id IS NOT NULL
        """
    )

    with op.batch_alter_table("curricula") as batch:
        batch.drop_column("description")
        batch.drop_column("publisher_id")

    op.create_index("ix_curricula_isbn", "curricula", ["isbn"])
    op.create_index("ix_curricula_barcode", "curricula", ["barcode"])

    op.drop_table("curriculum_page_mappings")
    op.drop_table("curriculum_units")
    op.drop_table("curriculum_resources")
    op.drop_table("curriculum_editions")
    op.drop_table("book_editions")
    op.drop_table("work_authors")
    op.drop_table("works")
    op.drop_table("authors")
    op.drop_table("publishers")
