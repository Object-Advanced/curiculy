"""Import a curriculum's structure from JSON or CSV.

Both formats are normalized into :class:`CurriculumImportRequest` before anything
touches the database, so there is one ingestion path and CSV cannot drift from
JSON.

An import is all or nothing. A spreadsheet with a bad page range on row 40 leaves
nothing behind, because a half-imported program still looks complete to the
pacing engine and would quietly pace against missing lessons. Problems that do
not threaten the structure — an ISBN that has not been scanned yet — are
collected as warnings on the summary instead, since the fix there is to resolve
the book, not to re-upload the file.

Re-importing is expected: a parent fixes a page number and uploads again. Units
are matched by title within their parent, and page mappings by unit and resource,
so a corrected file updates rows instead of duplicating the program.
"""

import csv
import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums import CurriculumSource, MappingSource, ResourceKind, UnitKind
from app.models import (
    BookEdition,
    Curriculum,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
)
from app.schemas.curriculum import (
    DEFAULT_EDITION_LABEL,
    CurriculumImportRequest,
    ImportResource,
    ImportSummary,
    ImportUnit,
)
from app.utils.isbn import barcode_to_isbn13, to_isbn13

# Spreadsheets are written by people, so the column a parent types is accepted
# under any of its obvious spellings.
CSV_COLUMNS: dict[str, tuple[str, ...]] = {
    "curriculum_name": ("curriculum_name", "curriculum", "curriculum_title", "program"),
    "publisher": ("publisher",),
    "subject": ("subject",),
    "edition": ("edition", "edition_label"),
    "grade_level": ("grade_level", "grade"),
    "copyright_year": ("copyright_year", "copyright"),
    "resource_type": ("resource_type", "resource_kind", "resource"),
    "resource_title": ("resource_title", "book_title"),
    "isbn13": ("isbn13", "isbn", "isbn_13"),
    "unit_title": ("unit_title", "title", "lesson_title", "lesson"),
    "unit_type": ("unit_type", "unit_kind", "kind"),
    "unit_label": ("unit_label", "label"),
    "parent_title": ("parent_title", "parent", "parent_unit"),
    "sequence": ("sequence", "sort_order", "order", "seq"),
    "start_page": ("start_page", "page_start", "from_page"),
    "end_page": ("end_page", "page_end", "to_page"),
    "printed_start_page": ("printed_start_page", "printed_page_start"),
    "printed_end_page": ("printed_end_page", "printed_page_end"),
    "estimated_minutes": ("estimated_minutes", "minutes"),
    "estimated_sessions": ("estimated_sessions", "sessions"),
    "notes": ("notes",),
}

_ALIAS_TO_COLUMN = {
    alias: column for column, aliases in CSV_COLUMNS.items() for alias in aliases
}

REQUIRED_CSV_COLUMNS = ("curriculum_name", "unit_title")


class CurriculumImportError(ValueError):
    """The payload could not be imported; nothing was written."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) or "the curriculum could not be imported")


def parse_csv(text: str) -> CurriculumImportRequest:
    """Turn a flat spreadsheet into the same request shape JSON posts.

    One file describes one curriculum edition. Rows that name a different program
    are rejected rather than guessed at, because silently splitting a file into
    two curricula is far harder to notice than an error message.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if reader.fieldnames is None:
        raise CurriculumImportError(["the CSV payload is empty"])

    columns = {
        column: original
        for original in reader.fieldnames
        if (column := _ALIAS_TO_COLUMN.get(_normalize_header(original))) is not None
    }
    missing = [name for name in REQUIRED_CSV_COLUMNS if name not in columns]
    if missing:
        raise CurriculumImportError(
            [f"the CSV is missing the required column(s): {', '.join(missing)}"]
        )

    rows: list[tuple[str, dict[str, str]]] = []
    for line_number, raw in enumerate(reader, start=2):
        row = {column: _cell(raw.get(original)) for column, original in columns.items()}
        if any(row.values()):
            rows.append((f"row {line_number}", row))
    if not rows:
        raise CurriculumImportError(["the CSV payload has no data rows"])

    errors: list[str] = []
    first_ref, first = rows[0]
    request_fields = {
        "curriculum_name": first["curriculum_name"],
        "publisher": first.get("publisher") or None,
        "subject": first.get("subject") or None,
        "edition": first.get("edition") or DEFAULT_EDITION_LABEL,
        "grade_level": first.get("grade_level") or None,
        "copyright_year": _int_cell(
            first.get("copyright_year"), first_ref, "copyright_year", errors
        ),
    }
    if not request_fields["curriculum_name"]:
        raise CurriculumImportError([f"{first_ref}: curriculum_name is required"])

    resources = _CsvResources()
    units_by_title: dict[str, ImportUnit] = {}
    roots: list[ImportUnit] = []

    for ref, row in rows:
        name = row["curriculum_name"]
        if name and name.casefold() != str(request_fields["curriculum_name"]).casefold():
            errors.append(
                f"{ref}: '{name}' does not match the curriculum '{request_fields['curriculum_name']}'; "
                "import one curriculum per file"
            )
            continue

        edition = row.get("edition")
        if edition and edition.casefold() != str(request_fields["edition"]).casefold():
            errors.append(
                f"{ref}: edition '{edition}' does not match '{request_fields['edition']}'; "
                "import one edition per file"
            )
            continue

        title = row["unit_title"]
        if not title:
            errors.append(f"{ref}: unit_title is required")
            continue

        kind = _enum_cell(row.get("unit_type"), UnitKind, UnitKind.LESSON, ref, "unit_type", errors)
        resource_kind = _enum_cell(
            row.get("resource_type"),
            ResourceKind,
            ResourceKind.STUDENT_TEXT,
            ref,
            "resource_type",
            errors,
        )
        resource_key = resources.register(
            kind=resource_kind,
            isbn13=row.get("isbn13") or None,
            title=row.get("resource_title") or None,
        )

        unit = ImportUnit(
            title=title,
            kind=kind,
            label=row.get("unit_label") or None,
            sequence=_int_cell(row.get("sequence"), ref, "sequence", errors),
            estimated_minutes=_int_cell(row.get("estimated_minutes"), ref, "estimated_minutes", errors),
            estimated_sessions=_int_cell(row.get("estimated_sessions"), ref, "estimated_sessions", errors),
            notes=row.get("notes") or None,
            resource=resource_key,
            page_start=_int_cell(row.get("start_page"), ref, "start_page", errors),
            page_end=_int_cell(row.get("end_page"), ref, "end_page", errors),
            printed_page_start=row.get("printed_start_page") or None,
            printed_page_end=row.get("printed_end_page") or None,
            source_ref=ref,
        )

        parent_title = row.get("parent_title")
        if parent_title:
            parent = units_by_title.get(parent_title.casefold())
            if parent is None:
                errors.append(
                    f"{ref}: parent unit '{parent_title}' is not defined on an earlier row"
                )
            else:
                parent.children.append(unit)
        else:
            roots.append(unit)
        units_by_title[title.casefold()] = unit

    if errors:
        raise CurriculumImportError(errors)

    return CurriculumImportRequest(
        **request_fields,
        resources=resources.specs(),
        units=roots,
    )


class _CsvResources:
    """Collects the distinct resources a flat CSV refers to, in first-seen order."""

    def __init__(self) -> None:
        self._specs: dict[str, ImportResource] = {}

    def register(
        self,
        kind: ResourceKind,
        isbn13: str | None,
        title: str | None,
    ) -> str:
        key = f"{kind.value}:{isbn13 or ''}"
        spec = self._specs.get(key)
        if spec is None:
            self._specs[key] = ImportResource(key=key, kind=kind, isbn13=isbn13, title=title)
        elif title and not spec.title:
            spec.title = title
        return key

    def specs(self) -> list[ImportResource]:
        return list(self._specs.values())


@dataclass
class _Counts:
    resources_created: int = 0
    units_created: int = 0
    units_updated: int = 0
    page_mappings_created: int = 0
    page_mappings_updated: int = 0


@dataclass
class _Run:
    """Per-import state, so the helpers below do not thread six arguments each."""

    counts: _Counts = field(default_factory=_Counts)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # A resource maps to None when the alias is ambiguous, which is reported as
    # an error only if a unit actually tries to use it.
    aliases: dict[str, CurriculumResource | None] = field(default_factory=dict)
    resources: list[CurriculumResource] = field(default_factory=list)


class CurriculumImporter:
    """Creates or updates a curriculum edition, its resources, and its unit tree."""

    def __init__(self, db: Session, catalog_db: Session | None = None) -> None:
        self._db = db
        self._catalog_db = catalog_db if catalog_db is not None else db

    def import_csv(self, text: str) -> ImportSummary:
        return self.import_payload(parse_csv(text))

    def import_payload(self, payload: CurriculumImportRequest) -> ImportSummary:
        try:
            summary = self._ingest(payload)
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise CurriculumImportError(
                [f"the import conflicts with existing catalog rows: {error.orig}"]
            ) from error
        except Exception:
            self._db.rollback()
            raise
        return summary

    def _ingest(self, payload: CurriculumImportRequest) -> ImportSummary:
        if not payload.units and not payload.resources:
            raise CurriculumImportError(["the payload has no units and no resources to import"])

        run = _Run()
        curriculum, curriculum_created = self._get_or_create_curriculum(payload)
        edition, edition_created = self._get_or_create_edition(curriculum, payload)
        self._sync_resources(edition, payload, run)
        self._sync_units(edition, payload.units, parent=None, depth=0, run=run)

        if run.errors:
            raise CurriculumImportError(run.errors)

        self._db.flush()
        return ImportSummary(
            curriculum_id=curriculum.id,
            curriculum_title=curriculum.title,
            curriculum_edition_id=edition.id,
            edition_label=edition.edition_label,
            curriculum_created=curriculum_created,
            edition_created=edition_created,
            resources_created=run.counts.resources_created,
            units_created=run.counts.units_created,
            units_updated=run.counts.units_updated,
            page_mappings_created=run.counts.page_mappings_created,
            page_mappings_updated=run.counts.page_mappings_updated,
            errors=run.warnings,
        )

    def _get_or_create_curriculum(
        self, payload: CurriculumImportRequest
    ) -> tuple[Curriculum, bool]:
        title = payload.curriculum_name.strip()
        curriculum = (
            self._db.execute(select(Curriculum).where(func.lower(Curriculum.title) == title.lower()))
            .scalars()
            .first()
        )
        created = curriculum is None
        if curriculum is None:
            curriculum = Curriculum(title=title, source_type=CurriculumSource.MANUAL)
            self._db.add(curriculum)

        if payload.publisher:
            curriculum.publisher_name = payload.publisher.strip()
        if payload.subject:
            curriculum.subject = payload.subject
        if payload.description:
            curriculum.description = payload.description

        self._db.flush()
        return curriculum, created

    def _get_or_create_edition(
        self,
        curriculum: Curriculum,
        payload: CurriculumImportRequest,
    ) -> tuple[CurriculumEdition, bool]:
        label = payload.edition.strip()
        edition = (
            self._db.execute(
                select(CurriculumEdition).where(
                    CurriculumEdition.curriculum_id == curriculum.id,
                    func.lower(CurriculumEdition.edition_label) == label.lower(),
                )
            )
            .scalars()
            .first()
        )
        created = edition is None
        if edition is None:
            edition = CurriculumEdition(curriculum_id=curriculum.id, edition_label=label)
            self._db.add(edition)

        if payload.copyright_year is not None:
            edition.copyright_year = payload.copyright_year
        if payload.grade_level:
            edition.grade_level = payload.grade_level
        edition.is_current = payload.is_current

        self._db.flush()
        return edition, created

    def _sync_resources(
        self,
        edition: CurriculumEdition,
        payload: CurriculumImportRequest,
        run: _Run,
    ) -> None:
        for index, spec in enumerate(payload.resources):
            label = spec.key or spec.title or spec.kind.value
            book_edition = self._book_edition_for(spec, label, run)
            title = spec.title or _default_resource_title(payload.curriculum_name, spec.kind)

            resource = (
                self._db.execute(
                    select(CurriculumResource).where(
                        CurriculumResource.curriculum_edition_id == edition.id,
                        CurriculumResource.kind == spec.kind,
                        func.lower(CurriculumResource.title) == title.lower(),
                    )
                )
                .scalars()
                .first()
            )
            if resource is None:
                resource = CurriculumResource(
                    curriculum_edition_id=edition.id,
                    kind=spec.kind,
                    title=title,
                )
                self._db.add(resource)
                run.counts.resources_created += 1

            if book_edition is not None:
                resource.book_edition_id = book_edition.id
            resource.is_required = spec.is_required
            resource.is_consumable = spec.is_consumable
            resource.sort_order = spec.sort_order if spec.sort_order is not None else index
            if spec.notes:
                resource.notes = spec.notes

            self._db.flush()
            run.resources.append(resource)
            for alias in _resource_aliases(spec, title, book_edition):
                run.aliases[alias] = None if alias in run.aliases else resource

    def _book_edition_for(
        self,
        spec: ImportResource,
        label: str,
        run: _Run,
    ) -> BookEdition | None:
        if not spec.isbn13:
            return None

        canonical = to_isbn13(spec.isbn13) or barcode_to_isbn13(spec.isbn13)
        if canonical is None:
            run.errors.append(f"resource '{label}': '{spec.isbn13}' is not a valid ISBN")
            return None

        book_edition = (
            self._catalog_db.execute(select(BookEdition).where(BookEdition.isbn13 == canonical))
            .scalars()
            .first()
        )
        if book_edition is None:
            run.warnings.append(
                f"resource '{label}': ISBN {canonical} is not in the local catalog yet, so no "
                "book was attached; resolve the ISBN and import again to link it"
            )
        return book_edition

    def _sync_units(
        self,
        edition: CurriculumEdition,
        specs: Sequence[ImportUnit],
        parent: CurriculumUnit | None,
        depth: int,
        run: _Run,
    ) -> None:
        for index, spec in enumerate(specs):
            unit = self._get_or_create_unit(edition, spec, parent, depth, index, run)
            self._sync_page_mapping(unit, spec, run)
            self._sync_units(edition, spec.children, parent=unit, depth=depth + 1, run=run)

    def _get_or_create_unit(
        self,
        edition: CurriculumEdition,
        spec: ImportUnit,
        parent: CurriculumUnit | None,
        depth: int,
        index: int,
        run: _Run,
    ) -> CurriculumUnit:
        parent_id = parent.id if parent is not None else None
        unit = (
            self._db.execute(
                select(CurriculumUnit).where(
                    CurriculumUnit.curriculum_edition_id == edition.id,
                    CurriculumUnit.parent_id.is_(None)
                    if parent_id is None
                    else CurriculumUnit.parent_id == parent_id,
                    func.lower(CurriculumUnit.title) == spec.title.lower(),
                )
            )
            .scalars()
            .first()
        )
        if unit is None:
            unit = CurriculumUnit(
                curriculum_edition_id=edition.id,
                parent_id=parent_id,
                title=spec.title,
            )
            self._db.add(unit)
            run.counts.units_created += 1
        else:
            run.counts.units_updated += 1

        unit.kind = spec.kind
        unit.label = spec.label
        unit.sort_order = spec.sequence if spec.sequence is not None else index
        unit.depth = depth
        unit.estimated_minutes = spec.estimated_minutes
        unit.estimated_sessions = spec.estimated_sessions
        unit.is_optional = spec.is_optional
        if spec.notes:
            unit.notes = spec.notes

        self._db.flush()
        return unit

    def _sync_page_mapping(self, unit: CurriculumUnit, spec: ImportUnit, run: _Run) -> None:
        pages = _page_range(spec, run.errors)
        if pages is None:
            return

        resource = self._resolve_resource(spec, run)
        if resource is None:
            return

        page_start, page_end = pages
        mapping = (
            self._db.execute(
                select(CurriculumPageMapping).where(
                    CurriculumPageMapping.curriculum_unit_id == unit.id,
                    CurriculumPageMapping.curriculum_resource_id == resource.id,
                )
            )
            .scalars()
            .first()
        )
        if mapping is None:
            mapping = CurriculumPageMapping(
                curriculum_unit_id=unit.id,
                curriculum_resource_id=resource.id,
                page_start=page_start,
                page_end=page_end,
            )
            self._db.add(mapping)
            run.counts.page_mappings_created += 1
        else:
            mapping.page_start = page_start
            mapping.page_end = page_end
            run.counts.page_mappings_updated += 1

        mapping.printed_page_start = spec.printed_page_start
        mapping.printed_page_end = spec.printed_page_end
        mapping.is_primary = True
        mapping.source = MappingSource.IMPORTED
        self._db.flush()

    def _resolve_resource(self, spec: ImportUnit, run: _Run) -> CurriculumResource | None:
        where = _locate(spec)
        if spec.resource:
            alias = spec.resource.strip().casefold()
            if alias not in run.aliases:
                run.errors.append(
                    f"{where}: no resource named '{spec.resource}' was declared in this import"
                )
                return None
            resource = run.aliases[alias]
            if resource is None:
                run.errors.append(
                    f"{where}: '{spec.resource}' matches more than one resource; give each "
                    "resource a distinct key"
                )
                return None
            return resource

        if len(run.resources) == 1:
            return run.resources[0]
        if not run.resources:
            run.errors.append(f"{where}: page numbers were given but the import declares no resource")
        else:
            run.errors.append(
                f"{where}: the import declares several resources, so the unit must name which "
                "one its pages refer to"
            )
        return None


def _page_range(spec: ImportUnit, errors: list[str]) -> tuple[int, int] | None:
    start, end = spec.page_start, spec.page_end
    if start is None and end is None:
        return None

    where = _locate(spec)
    if start is None:
        errors.append(f"{where}: end_page was given without start_page")
        return None
    if end is None:
        end = start
    if start < 1 or end < 1:
        errors.append(f"{where}: page numbers must be 1 or greater (got {start} to {end})")
        return None
    if end < start:
        errors.append(f"{where}: end_page {end} precedes start_page {start}")
        return None
    return start, end


def _locate(spec: ImportUnit) -> str:
    return spec.source_ref or f"unit '{spec.title}'"


def _resource_aliases(
    spec: ImportResource,
    title: str,
    book_edition: BookEdition | None,
) -> Iterable[str]:
    """Every string a unit may plausibly use to point at this resource."""
    candidates = [spec.key, title, spec.kind.value, spec.isbn13]
    if book_edition is not None:
        candidates.extend([book_edition.isbn13, book_edition.isbn10])
    return {candidate.strip().casefold() for candidate in candidates if candidate}


def _default_resource_title(curriculum_name: str, kind: ResourceKind) -> str:
    return f"{curriculum_name} {kind.value.replace('_', ' ').title()}"


def _normalize_header(name: str) -> str:
    cleaned = name.strip().lower().replace("-", " ").replace("_", " ")
    return "_".join(cleaned.split())


def _cell(value: str | None) -> str:
    return (value or "").strip()


def _int_cell(value: str | None, ref: str, column: str, errors: list[str]) -> int | None:
    text = _cell(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        errors.append(f"{ref}: {column} must be a whole number, not '{text}'")
        return None


def _enum_cell[E: StrEnum](
    value: str | None,
    enum_cls: type[E],
    default: E,
    ref: str,
    column: str,
    errors: list[str],
) -> E:
    text = _cell(value)
    if not text:
        return default
    candidate = text.lower().replace("-", "_").replace(" ", "_")
    try:
        return enum_cls(candidate)
    except ValueError:
        allowed = ", ".join(member.value for member in enum_cls)
        errors.append(f"{ref}: '{text}' is not a valid {column}; expected one of {allowed}")
        return default
