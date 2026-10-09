"""Reconcile historical Enrollment rows from assignment provenance.

Enrollment is student + curriculum + school year. Current pacing commit and
plan-apply already insert that trio. Assignments scheduled before that side
effect can still prove it when they carry a stored ``curriculum_id``, or a
live curriculum resource or unit whose edition still points at ``curricula``,
and their date falls in exactly one named school year.

Historical week/day plan-apply assignments that store only a title and date
are still refused. Do not infer a library row from lesson titles.

Not called from boot. Operators run ``scripts/backfill_enrollments.py``.
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import (
    Assignment,
    Curriculum,
    CurriculumEdition,
    CurriculumResource,
    CurriculumUnit,
    Enrollment,
    SchoolYear,
    Student,
)
from app.services.enrollments import ensure_enrollment


@dataclass
class EnrollmentBackfillReport:
    """Counts for one tenant file or in-memory session."""

    inserted: int = 0
    already_present: int = 0
    skipped_unlinked_assignments: int = 0
    skipped_orphan_links: int = 0
    skipped_no_year: int = 0
    skipped_ambiguous_year: int = 0
    skipped_missing_student: int = 0
    candidates: list[tuple[int, int, int]] = field(default_factory=list)
    dry_run: bool = True

    def format_lines(self, label: str) -> list[str]:
        action = "would insert" if self.dry_run else "inserted"
        lines = [
            f"{label}",
            f"  {action}: {self.inserted if not self.dry_run else len(self.candidates)}",
            f"  already present: {self.already_present}",
            f"  skipped unlinked assignments: {self.skipped_unlinked_assignments}",
            f"  skipped orphan resource/unit links: {self.skipped_orphan_links}",
            f"  skipped no matching school year: {self.skipped_no_year}",
            f"  skipped overlapping school years: {self.skipped_ambiguous_year}",
            f"  skipped missing student: {self.skipped_missing_student}",
        ]
        if self.dry_run:
            lines.append("  dry-run: no rows written")
        return lines


def _years_covering(day, years: list[SchoolYear]) -> list[SchoolYear]:
    return [year for year in years if year.start_date <= day <= year.end_date]


def _curriculum_maps(
    db: Session, resource_ids: set[int], unit_ids: set[int]
) -> tuple[dict[int, int], dict[int, int]]:
    resource_to_curriculum: dict[int, int] = {}
    if resource_ids:
        resource_to_curriculum = dict(
            db.execute(
                select(CurriculumResource.id, CurriculumEdition.curriculum_id)
                .join(
                    CurriculumEdition,
                    CurriculumResource.curriculum_edition_id == CurriculumEdition.id,
                )
                .join(Curriculum, Curriculum.id == CurriculumEdition.curriculum_id)
                .where(CurriculumResource.id.in_(resource_ids))
            ).all()
        )
    unit_to_curriculum: dict[int, int] = {}
    if unit_ids:
        unit_to_curriculum = dict(
            db.execute(
                select(CurriculumUnit.id, CurriculumEdition.curriculum_id)
                .join(
                    CurriculumEdition,
                    CurriculumUnit.curriculum_edition_id == CurriculumEdition.id,
                )
                .join(Curriculum, Curriculum.id == CurriculumEdition.curriculum_id)
                .where(CurriculumUnit.id.in_(unit_ids))
            ).all()
        )
    return resource_to_curriculum, unit_to_curriculum


def _curriculum_id_for_assignment(
    assignment: Assignment,
    resource_to_curriculum: dict[int, int],
    unit_to_curriculum: dict[int, int],
) -> int | None:
    if assignment.curriculum_id is not None:
        return assignment.curriculum_id
    curriculum_id = None
    if assignment.curriculum_resource_id is not None:
        curriculum_id = resource_to_curriculum.get(assignment.curriculum_resource_id)
    if curriculum_id is None and assignment.curriculum_unit_id is not None:
        curriculum_id = unit_to_curriculum.get(assignment.curriculum_unit_id)
    return curriculum_id


def discover_missing_enrollments(db: Session) -> EnrollmentBackfillReport:
    """Find student/curriculum/year triples that assignments can prove.

    Does not write. Does not guess unlinked plan-apply rows.
    """
    report = EnrollmentBackfillReport(dry_run=True)
    report.skipped_unlinked_assignments = (
        db.query(Assignment)
        .filter(
            Assignment.curriculum_id.is_(None),
            Assignment.curriculum_resource_id.is_(None),
            Assignment.curriculum_unit_id.is_(None),
        )
        .count()
    )
    linked = (
        db.query(Assignment)
        .filter(
            or_(
                Assignment.curriculum_id.isnot(None),
                Assignment.curriculum_resource_id.isnot(None),
                Assignment.curriculum_unit_id.isnot(None),
            )
        )
        .order_by(Assignment.id)
        .all()
    )
    if not linked:
        return report

    resource_ids = {
        row.curriculum_resource_id
        for row in linked
        if row.curriculum_resource_id is not None
    }
    unit_ids = {
        row.curriculum_unit_id for row in linked if row.curriculum_unit_id is not None
    }
    resource_to_curriculum, unit_to_curriculum = _curriculum_maps(
        db, resource_ids, unit_ids
    )
    years = db.query(SchoolYear).order_by(SchoolYear.id).all()
    student_ids = {row[0] for row in db.query(Student.id).all()}
    live_curriculum_ids = {row[0] for row in db.query(Curriculum.id).all()}
    existing = {
        (row.student_id, row.curriculum_id, row.school_year_id)
        for row in db.query(Enrollment).all()
    }
    seen_existing: set[tuple[int, int, int]] = set()
    seen_new: set[tuple[int, int, int]] = set()

    for assignment in linked:
        if assignment.student_id not in student_ids:
            report.skipped_missing_student += 1
            continue
        curriculum_id = _curriculum_id_for_assignment(
            assignment, resource_to_curriculum, unit_to_curriculum
        )
        if curriculum_id is None or curriculum_id not in live_curriculum_ids:
            report.skipped_orphan_links += 1
            continue
        covering = _years_covering(assignment.scheduled_date, years)
        if not covering:
            report.skipped_no_year += 1
            continue
        if len(covering) > 1:
            report.skipped_ambiguous_year += 1
            continue
        triple = (assignment.student_id, curriculum_id, covering[0].id)
        if triple in existing:
            if triple not in seen_existing:
                seen_existing.add(triple)
                report.already_present += 1
            continue
        if triple not in seen_new:
            seen_new.add(triple)
            report.candidates.append(triple)
    return report


def reconcile_enrollments(db: Session, *, dry_run: bool = True) -> EnrollmentBackfillReport:
    """Insert missing proven enrollments, or report them when ``dry_run``.

    Commits only when ``dry_run`` is false. Never updates or deletes enrollments,
    assignments, curricula, or school years.
    """
    report = discover_missing_enrollments(db)
    report.dry_run = dry_run
    if dry_run:
        return report
    try:
        for student_id, curriculum_id, school_year_id in report.candidates:
            ensure_enrollment(
                db,
                student_id=student_id,
                curriculum_id=curriculum_id,
                school_year_id=school_year_id,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    report.inserted = len(report.candidates)
    return report


def tenant_db_paths(data_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in data_dir.glob("tenant_*.db")
        if path.is_file() and path.name != "tenant.db"
    )


def _engine_for(path: Path) -> Engine:
    from sqlalchemy import create_engine

    return create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )


def backfill_tenant_file(path: Path, *, dry_run: bool = True) -> EnrollmentBackfillReport:
    from app.schema_patches import apply_tenant_schema

    engine = _engine_for(path)
    try:
        apply_tenant_schema(engine)
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        session = factory()
        try:
            return reconcile_enrollments(session, dry_run=dry_run)
        finally:
            session.close()
    finally:
        engine.dispose()


def backfill_data_dir(data_dir: Path, *, dry_run: bool = True) -> list[tuple[Path, EnrollmentBackfillReport]]:
    results: list[tuple[Path, EnrollmentBackfillReport]] = []
    for path in tenant_db_paths(data_dir):
        results.append((path, backfill_tenant_file(path, dry_run=dry_run)))
    return results


def _parse_args(argv: list[str] | None = None) -> Namespace:
    parser = ArgumentParser(
        description=(
            "Insert Enrollment rows for assignments that already prove "
            "student + curriculum + school year (stored curriculum_id or a "
            "live resource/unit). Does not guess week/day plan titles. "
            "Does not run at application startup."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("./data"),
        help="Directory of tenant_*.db files (container data is /data).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Insert missing rows. Without this flag the run is a dry-run.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print each student/curriculum/year triple that would be inserted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    data_dir = args.data_dir
    dry_run = not args.apply
    if not data_dir.is_dir():
        print(f"No data directory at {data_dir}")
        return 1
    paths = tenant_db_paths(data_dir)
    if not paths:
        print(f"No tenant_*.db files in {data_dir}")
        return 0
    for path, report in backfill_data_dir(data_dir, dry_run=dry_run):
        print("\n".join(report.format_lines(path.name)))
        if args.verbose:
            for student_id, curriculum_id, school_year_id in report.candidates:
                print(
                    f"  triple student={student_id} "
                    f"curriculum={curriculum_id} year={school_year_id}"
                )
    return 0
