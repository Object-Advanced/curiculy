"""Read the stored structure of a curriculum edition.

The unit tree is assembled in Python from one flat, fully eager-loaded query
rather than by walking ``CurriculumUnit.children``, which would issue a query per
node and order siblings arbitrarily.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    BookEdition,
    Curriculum,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
    Work,
    WorkAuthor,
)
from app.schemas.curriculum import (
    CurriculumResourceRead,
    CurriculumResourcesRead,
    CurriculumTreeRead,
    CurriculumUnitNode,
    PageMappingRead,
)


def select_edition(
    db: Session,
    curriculum: Curriculum,
    edition_id: int | None = None,
) -> CurriculumEdition | None:
    """Choose which revision to read: the one asked for, the current one, or the first."""
    editions = (
        db.execute(
            select(CurriculumEdition)
            .where(CurriculumEdition.curriculum_id == curriculum.id)
            .order_by(CurriculumEdition.id)
        )
        .scalars()
        .all()
    )
    if edition_id is not None:
        return next((edition for edition in editions if edition.id == edition_id), None)
    current = next((edition for edition in editions if edition.is_current), None)
    return current or (editions[0] if editions else None)


def load_tree(
    db: Session,
    curriculum: Curriculum,
    edition: CurriculumEdition,
) -> CurriculumTreeRead:
    units = (
        db.execute(
            select(CurriculumUnit)
            .options(
                selectinload(CurriculumUnit.page_mappings).selectinload(
                    CurriculumPageMapping.curriculum_resource
                )
            )
            .where(CurriculumUnit.curriculum_edition_id == edition.id)
            .order_by(CurriculumUnit.sort_order, CurriculumUnit.id)
        )
        .scalars()
        .all()
    )

    known = {unit.id for unit in units}
    children: dict[int | None, list[CurriculumUnit]] = defaultdict(list)
    for unit in units:
        # A unit whose parent is not in this edition is shown at the root rather
        # than dropped, so bad data stays visible instead of silently vanishing.
        parent_id = unit.parent_id if unit.parent_id in known else None
        children[parent_id].append(unit)

    return CurriculumTreeRead(
        curriculum_id=curriculum.id,
        curriculum_title=curriculum.title,
        curriculum_edition_id=edition.id,
        edition_label=edition.edition_label,
        units=[_node(unit, children) for unit in children[None]],
    )


def _node(
    unit: CurriculumUnit,
    children: dict[int | None, list[CurriculumUnit]],
) -> CurriculumUnitNode:
    return CurriculumUnitNode(
        id=unit.id,
        parent_id=unit.parent_id,
        kind=unit.kind,
        label=unit.label,
        title=unit.title,
        sort_order=unit.sort_order,
        depth=unit.depth,
        estimated_minutes=unit.estimated_minutes,
        estimated_sessions=unit.estimated_sessions,
        is_optional=unit.is_optional,
        notes=unit.notes,
        page_mappings=[
            PageMappingRead.model_validate(mapping)
            for mapping in sorted(unit.page_mappings, key=lambda item: item.page_start)
        ],
        children=[_node(child, children) for child in children[unit.id]],
    )


def load_resources(
    db: Session,
    curriculum: Curriculum,
    edition: CurriculumEdition,
    catalog_db: Session | None = None,
) -> CurriculumResourcesRead:
    resources = (
        db.execute(
            select(CurriculumResource)
            .where(CurriculumResource.curriculum_edition_id == edition.id)
            .order_by(CurriculumResource.sort_order, CurriculumResource.id)
        )
        .scalars()
        .all()
    )
    attach_book_editions(resources, catalog_db)

    return CurriculumResourcesRead(
        curriculum_id=curriculum.id,
        curriculum_title=curriculum.title,
        curriculum_edition_id=edition.id,
        edition_label=edition.edition_label,
        resources=[CurriculumResourceRead.model_validate(resource) for resource in resources],
    )


def attach_book_editions(
    resources: list[CurriculumResource],
    catalog_db: Session | None,
) -> None:
    """Copy shared BookEdition rows onto household resources for the read models."""
    if catalog_db is None or not resources:
        return
    book_ids = {
        resource.book_edition_id
        for resource in resources
        if resource.book_edition_id is not None
    }
    if not book_ids:
        return
    books = {
        book.id: book
        for book in catalog_db.execute(
            select(BookEdition)
            .options(
                selectinload(BookEdition.publisher),
                selectinload(BookEdition.work).selectinload(Work.publisher),
                selectinload(BookEdition.work)
                .selectinload(Work.author_links)
                .selectinload(WorkAuthor.author),
            )
            .where(BookEdition.id.in_(book_ids))
        )
        .scalars()
        .all()
    }
    for resource in resources:
        if resource.book_edition_id is not None:
            resource.book_edition = books.get(resource.book_edition_id)
