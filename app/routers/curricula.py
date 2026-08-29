"""Curriculum endpoints.

``POST /curricula/import`` accepts the structure in whichever form the caller
already has it: a JSON document, a raw CSV body, or an uploaded file. The format
is taken from the content type, falling back to sniffing the first character so
a file posted without a useful type still works.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_catalog_db, get_tenant_db
from app.enums import MappingSource
from app.models import (
    Assignment,
    Curriculum,
    CurriculumEdition,
    CurriculumPageMapping,
    CurriculumResource,
    CurriculumUnit,
    Enrollment,
    ScheduledWork,
)
from app.schemas import (
    CurriculumCreate,
    CurriculumImportRequest,
    CurriculumRead,
    CurriculumResourcesRead,
    CurriculumTreeRead,
    ImportSummary,
)
from app.services.catalog import create_curriculum as persist_curriculum
from app.services.curriculum_import import CurriculumImporter, CurriculumImportError
from app.services.curriculum_structure import load_resources, load_tree, select_edition

router = APIRouter(
    prefix="/curricula",
    tags=["curricula"],
    dependencies=[Depends(require_parent)],
)

JSON_CONTENT_TYPES = {"application/json", "text/json"}
CSV_CONTENT_TYPES = {"text/csv", "application/csv"}
# Says "this is text" without saying which format, so the body decides.
SNIFFED_CONTENT_TYPES = {"text/plain"}

# Shown in the API docs, where a worked example explains the nesting faster than
# a schema does.
IMPORT_EXAMPLE = {
    "curriculum_name": "Saxon Math 5/4",
    "publisher": "Saxon Publishers",
    "subject": "Mathematics",
    "edition": "3rd edition",
    "grade_level": "4",
    "resources": [
        {"key": "text", "kind": "student_text", "title": "Student Text", "isbn13": "9781565775039"}
    ],
    "units": [
        {
            "title": "Section 1",
            "kind": "section",
            "children": [
                {
                    "title": "Lesson 1: Sequences",
                    "kind": "lesson",
                    "resource": "text",
                    "page_start": 1,
                    "page_end": 4,
                }
            ],
        }
    ],
}


@router.get("", response_model=list[CurriculumRead])
def list_curricula(tenant_db: Session = Depends(get_tenant_db)) -> list[Curriculum]:
    curricula = tenant_db.query(Curriculum).order_by(Curriculum.id).all()
    _stamp_scheduled(tenant_db, curricula)
    return curricula


@router.post("", response_model=CurriculumRead, status_code=201)
def create_curriculum(
    payload: CurriculumCreate,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> Curriculum:
    try:
        curriculum = persist_curriculum(tenant_db, catalog_db, payload)
        catalog_db.commit()
        tenant_db.commit()
        tenant_db.refresh(curriculum)
        curriculum.is_scheduled = False
        return curriculum
    except ValueError as error:
        catalog_db.rollback()
        tenant_db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception:
        catalog_db.rollback()
        tenant_db.rollback()
        raise


@router.post(
    "/import",
    response_model=ImportSummary,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {"type": "object"},
                    "example": IMPORT_EXAMPLE,
                },
                "text/csv": {"schema": {"type": "string"}},
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                        "required": ["file"],
                    }
                },
            },
            "required": True,
        }
    },
)
async def import_curriculum(
    request: Request,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> ImportSummary:
    fmt, text = await _import_source(request)
    importer = CurriculumImporter(tenant_db, catalog_db)
    try:
        if fmt == "csv":
            return importer.import_csv(text)
        return importer.import_payload(CurriculumImportRequest.model_validate_json(text))
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"message": "The import payload is malformed", "errors": _describe(error)},
        ) from error
    except CurriculumImportError as error:
        raise HTTPException(
            status_code=400,
            detail={"message": "The curriculum could not be imported", "errors": error.errors},
        ) from error


@router.get("/{curriculum_id}", response_model=CurriculumRead)
def get_curriculum(
    curriculum_id: int,
    tenant_db: Session = Depends(get_tenant_db),
) -> Curriculum:
    curriculum = _get_curriculum(tenant_db, curriculum_id)
    _stamp_scheduled(tenant_db, [curriculum])
    return curriculum


@router.delete("/{curriculum_id}/schedule", status_code=204)
def unschedule_curriculum(
    curriculum_id: int,
    tenant_db: Session = Depends(get_tenant_db),
) -> Response:
    """Drop this book's calendar work; the catalog entry itself stays.

    Assignments come off the calendar, and the generated syllabus units go with
    them, so Auto-schedule can write a fresh term later. The curriculum, its
    editions, resources, and linked books are left intact.
    """
    curriculum = _get_curriculum(tenant_db, curriculum_id)
    _clear_schedule(tenant_db, curriculum)
    tenant_db.commit()
    return Response(status_code=204)


@router.delete("/{curriculum_id}", status_code=204)
def delete_curriculum(
    curriculum_id: int,
    tenant_db: Session = Depends(get_tenant_db),
) -> Response:
    """Remove an unused curriculum, its editions, and its resources.

    Linked books stay in the catalog. Scheduled work has to be cleared first so
    a student's calendar is never emptied as a side effect of deleting a book.
    """
    curriculum = _get_curriculum(tenant_db, curriculum_id)
    if _scheduled_curriculum_ids(tenant_db, [curriculum.id]):
        raise HTTPException(
            status_code=409,
            detail="Unschedule this curriculum before deleting it",
        )
    _delete_enrollments(tenant_db, curriculum.id)
    tenant_db.delete(curriculum)
    tenant_db.commit()
    return Response(status_code=204)


@router.get("/{curriculum_id}/tree", response_model=CurriculumTreeRead)
def get_curriculum_tree(
    curriculum_id: int,
    edition_id: int | None = None,
    tenant_db: Session = Depends(get_tenant_db),
) -> CurriculumTreeRead:
    curriculum = _get_curriculum(tenant_db, curriculum_id)
    edition = _get_edition(tenant_db, curriculum, edition_id)
    return load_tree(tenant_db, curriculum, edition)


@router.get("/{curriculum_id}/resources", response_model=CurriculumResourcesRead)
def get_curriculum_resources(
    curriculum_id: int,
    edition_id: int | None = None,
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> CurriculumResourcesRead:
    curriculum = _get_curriculum(tenant_db, curriculum_id)
    edition = _get_edition(tenant_db, curriculum, edition_id)
    return load_resources(tenant_db, curriculum, edition, catalog_db)


def _get_curriculum(db: Session, curriculum_id: int) -> Curriculum:
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return curriculum


def _edition_ids(db: Session, curriculum_id: int) -> list[int]:
    return [
        edition_id
        for (edition_id,) in db.query(CurriculumEdition.id)
        .filter(CurriculumEdition.curriculum_id == curriculum_id)
        .all()
    ]


def _scheduled_curriculum_ids(tenant_db: Session, curriculum_ids: list[int]) -> set[int]:
    """Curricula that have at least one assignment hanging off a resource or unit."""
    if not curriculum_ids:
        return set()

    resource_map = {
        resource_id: curriculum_id
        for resource_id, curriculum_id in (
            tenant_db.query(CurriculumResource.id, CurriculumEdition.curriculum_id)
            .join(
                CurriculumEdition,
                CurriculumResource.curriculum_edition_id == CurriculumEdition.id,
            )
            .filter(CurriculumEdition.curriculum_id.in_(curriculum_ids))
            .all()
        )
    }
    unit_map = {
        unit_id: curriculum_id
        for unit_id, curriculum_id in (
            tenant_db.query(CurriculumUnit.id, CurriculumEdition.curriculum_id)
            .join(
                CurriculumEdition,
                CurriculumUnit.curriculum_edition_id == CurriculumEdition.id,
            )
            .filter(CurriculumEdition.curriculum_id.in_(curriculum_ids))
            .all()
        )
    }

    scheduled: set[int] = set()
    if resource_map:
        for (resource_id,) in (
            tenant_db.query(Assignment.curriculum_resource_id)
            .filter(Assignment.curriculum_resource_id.in_(resource_map))
            .distinct()
            .all()
        ):
            if resource_id is not None:
                scheduled.add(resource_map[resource_id])
    if unit_map:
        for (unit_id,) in (
            tenant_db.query(Assignment.curriculum_unit_id)
            .filter(Assignment.curriculum_unit_id.in_(unit_map))
            .distinct()
            .all()
        ):
            if unit_id is not None:
                scheduled.add(unit_map[unit_id])
    return scheduled


def _stamp_scheduled(tenant_db: Session, curricula: list[Curriculum]) -> None:
    scheduled = _scheduled_curriculum_ids(tenant_db, [item.id for item in curricula])
    for item in curricula:
        item.is_scheduled = item.id in scheduled


def _assignments_for_curriculum(tenant_db: Session, curriculum_id: int) -> list[Assignment]:
    edition_ids = _edition_ids(tenant_db, curriculum_id)
    if not edition_ids:
        return []

    resource_ids = [
        resource_id
        for (resource_id,) in tenant_db.query(CurriculumResource.id)
        .filter(CurriculumResource.curriculum_edition_id.in_(edition_ids))
        .all()
    ]
    unit_ids = [
        unit_id
        for (unit_id,) in tenant_db.query(CurriculumUnit.id)
        .filter(CurriculumUnit.curriculum_edition_id.in_(edition_ids))
        .all()
    ]
    clauses = []
    if resource_ids:
        clauses.append(Assignment.curriculum_resource_id.in_(resource_ids))
    if unit_ids:
        clauses.append(Assignment.curriculum_unit_id.in_(unit_ids))
    if not clauses:
        return []
    query = tenant_db.query(Assignment)
    if len(clauses) == 1:
        return query.filter(clauses[0]).all()
    return query.filter(clauses[0] | clauses[1]).all()


def _generated_unit_ids(db: Session, edition_ids: list[int]) -> set[int]:
    """Units written by auto-schedule: AI-parsed page mappings, plus empty course parents."""
    if not edition_ids:
        return set()

    generated = {
        unit_id
        for (unit_id,) in (
            db.query(CurriculumPageMapping.curriculum_unit_id)
            .join(
                CurriculumUnit,
                CurriculumUnit.id == CurriculumPageMapping.curriculum_unit_id,
            )
            .filter(
                CurriculumUnit.curriculum_edition_id.in_(edition_ids),
                CurriculumPageMapping.source == MappingSource.AI_PARSED,
            )
            .all()
        )
    }
    if not generated:
        return set()

    parents = {
        parent_id
        for (parent_id,) in db.query(CurriculumUnit.parent_id)
        .filter(CurriculumUnit.id.in_(generated), CurriculumUnit.parent_id.isnot(None))
        .all()
    }
    if not parents:
        return generated

    # Only drop a parent when every child is generated, so an imported tree that
    # later gained a few auto-scheduled lessons keeps its original structure.
    keep_parents = {
        parent_id
        for (parent_id,) in db.query(CurriculumUnit.parent_id)
        .filter(
            CurriculumUnit.parent_id.in_(parents),
            ~CurriculumUnit.id.in_(generated),
        )
        .all()
        if parent_id is not None
    }
    return generated | (parents - keep_parents)


def _with_orphaned_parents(db: Session, unit_ids: set[int]) -> set[int]:
    """Include parents whose remaining children are all in ``unit_ids``."""
    if not unit_ids:
        return unit_ids
    parents = {
        parent_id
        for (parent_id,) in db.query(CurriculumUnit.parent_id)
        .filter(CurriculumUnit.id.in_(unit_ids), CurriculumUnit.parent_id.isnot(None))
        .all()
    }
    if not parents:
        return unit_ids
    keep_parents = {
        parent_id
        for (parent_id,) in db.query(CurriculumUnit.parent_id)
        .filter(
            CurriculumUnit.parent_id.in_(parents),
            ~CurriculumUnit.id.in_(unit_ids),
        )
        .all()
        if parent_id is not None
    }
    return unit_ids | (parents - keep_parents)


def _clear_schedule(tenant_db: Session, curriculum: Curriculum) -> None:
    assignments = _assignments_for_curriculum(tenant_db, curriculum.id)
    unit_ids_from_assignments = {
        assignment.curriculum_unit_id
        for assignment in assignments
        if assignment.curriculum_unit_id is not None
    }
    for assignment in assignments:
        tenant_db.delete(assignment)

    edition_ids = _edition_ids(tenant_db, curriculum.id)
    generated_ids = _generated_unit_ids(tenant_db, edition_ids) | unit_ids_from_assignments
    generated_ids = _with_orphaned_parents(tenant_db, generated_ids)
    if not generated_ids:
        return

    work_rows = (
        tenant_db.query(ScheduledWork).filter(ScheduledWork.unit_id.in_(generated_ids)).all()
    )
    for row in work_rows:
        tenant_db.delete(row)

    units = tenant_db.query(CurriculumUnit).filter(CurriculumUnit.id.in_(generated_ids)).all()
    generated_id_set = generated_ids
    roots = [
        unit
        for unit in units
        if unit.parent_id is None or unit.parent_id not in generated_id_set
    ]
    already = {unit.id for unit in roots}
    for unit in units:
        if unit.id not in already:
            tenant_db.delete(unit)
    for unit in roots:
        tenant_db.delete(unit)


def _delete_enrollments(tenant_db: Session, curriculum_id: int) -> None:
    enrollments = (
        tenant_db.query(Enrollment).filter(Enrollment.curriculum_id == curriculum_id).all()
    )
    enrollment_ids = [row.id for row in enrollments]
    if enrollment_ids:
        for row in (
            tenant_db.query(ScheduledWork)
            .filter(ScheduledWork.enrollment_id.in_(enrollment_ids))
            .all()
        ):
            tenant_db.delete(row)
    for enrollment in enrollments:
        tenant_db.delete(enrollment)


def _get_edition(db: Session, curriculum: Curriculum, edition_id: int | None):
    edition = select_edition(db, curriculum, edition_id)
    if edition is None:
        detail = (
            f"Edition {edition_id} does not belong to this curriculum"
            if edition_id is not None
            else "This curriculum has no editions yet"
        )
        raise HTTPException(status_code=404, detail=detail)
    return edition


async def _import_source(request: Request) -> tuple[str, str]:
    """Return the payload as ``("json" | "csv", text)``."""
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

    if content_type == "multipart/form-data":
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(status_code=400, detail="Attach the import as a 'file' field")
        text = _decode(await upload.read())
        filename = (upload.filename or "").lower()
        if filename.endswith(".csv"):
            return "csv", text
        if filename.endswith(".json"):
            return "json", text
        return _sniff(text), text

    body = await request.body()
    if not body.strip():
        raise HTTPException(status_code=400, detail="The import payload is empty")
    text = _decode(body)

    if content_type in JSON_CONTENT_TYPES:
        return "json", text
    if content_type in CSV_CONTENT_TYPES:
        return "csv", text
    if content_type in SNIFFED_CONTENT_TYPES or not content_type:
        return _sniff(text), text
    raise HTTPException(
        status_code=415,
        detail=(
            f"Cannot import '{content_type}'; send application/json, text/csv, "
            "or a multipart file"
        ),
    )


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="The import payload must be UTF-8 text",
        ) from error


def _sniff(text: str) -> str:
    return "json" if text.lstrip()[:1] in {"{", "["} else "csv"


def _describe(error: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in item['loc']) or 'payload'}: {item['msg']}"
        for item in error.errors()
    ]
