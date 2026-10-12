"""The admin review queue for the community catalog (Settings → Admin).

At launch every contribution is reviewed. Each shows its flags, a comparison
with the catalog entry it changes or repeats (and the book lookup), and the
uploaded cover. Actions: approve, approve with edits, merge into an existing
entry, reject with a reason, or ask the contributor.

Every entry is versioned: approving a correction adds a version, and a
rollback adds a version copying an older one, so nothing is lost. Families
who use an entry keep their own copy; nothing is changed under them.

Approving links the contributor's own library item (or curriculum) to the
entry, and the family is told in their notifications, through a session
scoped to that one family (``open_family``).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import open_family_session
from app.enums import ParentNotificationType
from app.evidence import publish_cover
from app.models import (
    CatalogContribution,
    CatalogEntry,
    CatalogEntryVersion,
    CommunityCurriculum,
    CommunityCurriculumItem,
    LibraryItem,
    PlannedCurriculum,
)
from app.models.community import APPROVED, ASKED, MERGED, OPEN_STATUSES, REJECTED
from app.reference.subjects import SUBJECTS_BY_CODE
from app.schemas.community import (
    ApproveRequest,
    CatalogEdits,
    ContributionChanges,
    ContributionDetail,
    ContributionSummary,
    ContributorRead,
    EntryAdminRead,
    EntryVersionRead,
    FieldChange,
    FlagRead,
    LookupBook,
    MergeRequest,
    ReviewResult,
)
from app.services import community
from app.services.community_checks import REVIEW, normalize_publisher
from app.services.library_rules import KINDS
from app.services.notifications import create_notification
from app.utils.isbn import to_isbn13

logger = logging.getLogger(__name__)

FamilyOpener = Callable[[str], AbstractContextManager[Session]]


@contextmanager
def open_family(family: str) -> Iterator[Session]:
    """A session scoped to the contributing family (row-level security applies)."""
    session = open_family_session(family)
    try:
        yield session
    finally:
        session.close()


def contributor_label(family: str) -> str:
    return "Family " + hashlib.sha256(family.encode()).hexdigest()[:6]


# --- Reading the queue --------------------------------------------------------

def get_contribution(catalog_db: Session, contribution_id: int) -> CatalogContribution:
    contribution = catalog_db.get(CatalogContribution, contribution_id)
    if contribution is None:
        raise HTTPException(status_code=404, detail="No such contribution")
    return contribution


def _kind_label(contribution: CatalogContribution) -> str:
    if contribution.kind == community.CURRICULUM:
        return "Curriculum"
    return KINDS.get(contribution.item_kind or "", "Item")


def contribution_summary(contribution: CatalogContribution) -> ContributionSummary:
    return ContributionSummary(
        id=contribution.id,
        kind=contribution.kind,
        item_kind=contribution.item_kind,
        kind_label=_kind_label(contribution),
        title=contribution.title,
        isbn=contribution.isbn,
        status=contribution.status,
        needs_review=contribution.needs_review,
        is_correction=contribution.entry_id is not None,
        has_cover=bool(contribution.cover_path),
        contributor_label=contributor_label(contribution.contributor),
        review_flags=sum(1 for flag in contribution.flags if flag.level == REVIEW),
        notes=sum(1 for flag in contribution.flags if flag.level != REVIEW),
        created_at=contribution.created_at,
        updated_at=contribution.updated_at,
    )


def list_contributions(
    catalog_db: Session, status: str | None = None, kind: str | None = None, limit: int = 200
) -> list[ContributionSummary]:
    query = select(CatalogContribution)
    if status == "open" or status is None:
        query = query.where(CatalogContribution.status.in_(OPEN_STATUSES))
    elif status != "all":
        query = query.where(CatalogContribution.status == status)
    if kind:
        query = query.where(CatalogContribution.kind == kind)
    # Oldest first: the queue is first come, first reviewed.
    rows = catalog_db.scalars(query.order_by(CatalogContribution.created_at, CatalogContribution.id).limit(limit))
    return [contribution_summary(row) for row in rows]


def changes_between(old: dict, new: dict) -> ContributionChanges:
    fields = [
        FieldChange(field=name, catalog=old.get(name), contributed=new.get(name))
        for name in sorted(set(old) | set(new))
        if name not in {"chapters", "lessons", "items"} and old.get(name) != new.get(name)
    ]
    before, after = old.get("lessons") or [], new.get("lessons") or []
    changed = []
    for index in range(max(len(before), len(after))):
        a = before[index] if index < len(before) else None
        b = after[index] if index < len(after) else None
        if a != b:
            number = (b or a or {}).get("number")
            changed.append(str(number) if number is not None else f"#{index + 1}")
    return ContributionChanges(
        summary=community.describe_changes(old, new),
        fields=fields,
        chapters_before=len(old.get("chapters") or []),
        chapters_after=len(new.get("chapters") or []),
        lessons_before=len(before),
        lessons_after=len(after),
        lessons_changed=changed[:50],
    )


def _contributor(catalog_db: Session, family: str) -> ContributorRead:
    rows = catalog_db.execute(
        select(CatalogContribution.status, func.count())
        .where(CatalogContribution.contributor == family)
        .group_by(CatalogContribution.status)
    ).all()
    counts = dict(rows)
    return ContributorRead(
        label=contributor_label(family),
        accepted=counts.get(APPROVED, 0) + counts.get(MERGED, 0),
        rejected=counts.get(REJECTED, 0),
        total=sum(counts.values()),
    )


def contribution_detail(catalog_db: Session, contribution: CatalogContribution) -> ContributionDetail:
    compare = None
    if contribution.entry_id is not None:
        compare = catalog_db.get(CatalogEntry, contribution.entry_id)
    elif contribution.kind == community.ITEM:
        compare = community.find_duplicate(catalog_db, contribution.data)
    changes = None
    if compare is not None:
        changes = changes_between(community.current_version(catalog_db, compare).data, contribution.data)
    cached = community._cached_book(catalog_db, contribution.isbn)
    return ContributionDetail(
        **contribution_summary(contribution).model_dump(),
        data=contribution.data,
        flags=[FlagRead(code=f.code, group=f.group, level=f.level, where=f.where, message=f.message)
               for f in contribution.flags],
        compare_entry=community.entry_summary(compare) if compare is not None else None,
        changes=changes,
        lookup=LookupBook(title=cached.title, authors=cached.authors, page_count=cached.page_count) if cached else None,
        cover_url=f"/api/admin/community/contributions/{contribution.id}/cover" if contribution.cover_path else None,
        contributor=_contributor(catalog_db, contribution.contributor),
        review_note=contribution.review_note,
        reviewed_by=contribution.reviewed_by,
        reviewed_at=contribution.reviewed_at,
        result_entry_id=contribution.result_entry_id,
        result_curriculum_id=contribution.result_curriculum_id,
    )


# --- Writing entries ----------------------------------------------------------

def apply_edits(data: dict, edits: CatalogEdits | None) -> dict:
    result = dict(data)
    if edits is not None:
        for name, value in edits.model_dump(exclude_unset=True).items():
            if name in {"chapters", "lessons"}:
                continue
            result[name] = value
        if edits.chapters is not None:
            result["chapters"] = [chapter.model_dump() for chapter in edits.chapters]
        if edits.lessons is not None:
            result["lessons"] = [lesson.model_dump() for lesson in edits.lessons]
    if result.get("publisher"):
        result["publisher"] = normalize_publisher(result["publisher"])
    if result.get("isbn"):
        result["isbn"] = to_isbn13(result["isbn"]) or result["isbn"]
    return result


def _write_entry_fields(entry: CatalogEntry, data: dict) -> None:
    entry.kind = data["kind"]
    entry.title = data["title"]
    entry.title_key = community.title_key(data["title"])
    entry.author = data.get("author")
    entry.publisher = data.get("publisher")
    entry.edition = data.get("edition")
    entry.isbn = to_isbn13(data.get("isbn"))
    entry.subject_code = data.get("subject_code")
    entry.grade = data.get("grade")
    entry.total_pages = data.get("total_pages")
    entry.chapters_count = len(data.get("chapters") or [])
    entry.lessons_count = len(data.get("lessons") or [])
    if data.get("cover_url"):
        entry.cover_url = data["cover_url"]


def add_version(
    catalog_db: Session,
    entry: CatalogEntry,
    data: dict,
    *,
    admin: str,
    contribution_id: int | None = None,
    note: str | None = None,
) -> CatalogEntryVersion:
    latest = catalog_db.scalar(
        select(func.max(CatalogEntryVersion.version)).where(CatalogEntryVersion.entry_id == entry.id)
    ) if entry.id else None
    version = CatalogEntryVersion(
        version=(latest or 0) + 1,
        data=data,
        data_hash=community.data_hash(data),
        contribution_id=contribution_id,
        approved_by=admin,
        note=note,
    )
    entry.versions.append(version)
    entry.current_version = version.version
    _write_entry_fields(entry, data)
    catalog_db.flush()
    return version


def _take_cover(entry: CatalogEntry, contribution: CatalogContribution) -> bool:
    if not contribution.cover_path:
        return False
    published = publish_cover(contribution.cover_path, family=contribution.contributor)
    if published is None:
        return False
    entry.cover_path = published
    entry.cover_hash = contribution.cover_hash
    return True


def _tell_family(open_family: FamilyOpener, family: str, change: Callable[[Session], None]) -> None:
    """Link the family's own copy and leave them a note. A failure here never
    undoes the review; it's logged."""
    try:
        with open_family(family) as session:
            change(session)
            session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Could not update the contributing family after a catalog review")


def _notify(session: Session, title: str, body: str) -> None:
    create_notification(
        session, type=ParentNotificationType.CATALOG_UPDATE, student_id=None, assignment_id=None,
        title=title, body=body,
    )


def _link_item(
    open_family: FamilyOpener,
    contribution: CatalogContribution,
    entry: CatalogEntry,
    *,
    cover: str | None,
    message: tuple[str, str] | None,
) -> None:
    def change(session: Session) -> None:
        item = session.get(LibraryItem, contribution.source_id)
        if item is not None:
            item.catalog_entry_id = entry.id
            item.catalog_version = entry.current_version
            if cover:
                item.cover_review = cover
        if message:
            _notify(session, *message)

    _tell_family(open_family, contribution.contributor, change)


def _require_open(contribution: CatalogContribution) -> None:
    if contribution.status not in OPEN_STATUSES:
        raise HTTPException(status_code=409, detail=f"This contribution was already {contribution.status}.")


def _close(contribution: CatalogContribution, status: str, admin: str, note: str | None) -> None:
    contribution.status = status
    contribution.reviewed_by = admin
    contribution.reviewed_at = func.now()
    contribution.review_note = note


def _thanks(title: str) -> tuple[str, str]:
    return (
        "Added to the Curiculy catalog",
        f'Thank you! "{title}" is now in the Curiculy catalog, so other families can add it in seconds.',
    )


# --- Review actions -----------------------------------------------------------

def approve(
    catalog_db: Session,
    contribution: CatalogContribution,
    request: ApproveRequest,
    *,
    admin: str,
    open_family: FamilyOpener,
) -> ReviewResult:
    _require_open(contribution)
    if contribution.kind == community.CURRICULUM:
        return _approve_curriculum(catalog_db, contribution, request, admin=admin, open_family=open_family)

    data = apply_edits(contribution.data, request.edits)
    entry = catalog_db.get(CatalogEntry, contribution.entry_id) if contribution.entry_id else None
    if entry is None:
        entry = CatalogEntry(families_count=1, current_version=0, status="published")
        catalog_db.add(entry)
        _write_entry_fields(entry, data)
        catalog_db.flush()
        add_version(catalog_db, entry, data, admin=admin, contribution_id=contribution.id, note=request.note)
    elif community.data_hash(data) != community.current_version(catalog_db, entry).data_hash:
        add_version(catalog_db, entry, data, admin=admin, contribution_id=contribution.id, note=request.note)
    took_cover = request.include_cover and _take_cover(entry, contribution)
    _close(contribution, APPROVED, admin, request.note)
    contribution.result_entry_id = entry.id
    catalog_db.commit()

    cover = ("approved" if took_cover else "rejected") if contribution.cover_path else None
    _link_item(open_family, contribution, entry, cover=cover, message=_thanks(entry.title))
    return ReviewResult(contribution=contribution_detail(catalog_db, contribution), entry_id=entry.id)


def merge(
    catalog_db: Session,
    contribution: CatalogContribution,
    request: MergeRequest,
    *,
    admin: str,
    open_family: FamilyOpener,
) -> ReviewResult:
    """Another family entered a book the catalog already has: count it, and
    optionally take its details as the entry's new version."""
    _require_open(contribution)
    if contribution.kind != community.ITEM:
        raise HTTPException(status_code=409, detail="Only books can be merged into a catalog entry.")
    entry = catalog_db.get(CatalogEntry, request.entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="No such catalog entry")
    if entry.kind != contribution.item_kind:
        raise HTTPException(status_code=409, detail="That entry is a different kind of book.")
    if request.replace_details:
        add_version(catalog_db, entry, apply_edits(contribution.data, None), admin=admin,
                    contribution_id=contribution.id, note=request.note)
    if contribution.entry_id != entry.id:
        entry.families_count += 1
    took_cover = request.include_cover and _take_cover(entry, contribution)
    _close(contribution, MERGED, admin, request.note)
    contribution.result_entry_id = entry.id
    catalog_db.commit()

    cover = ("approved" if took_cover else "rejected") if contribution.cover_path else None
    _link_item(open_family, contribution, entry, cover=cover, message=_thanks(entry.title))
    return ReviewResult(contribution=contribution_detail(catalog_db, contribution), entry_id=entry.id)


def reject(
    catalog_db: Session, contribution: CatalogContribution, reason: str, *, admin: str, open_family: FamilyOpener
) -> ReviewResult:
    _require_open(contribution)
    _close(contribution, REJECTED, admin, reason)
    catalog_db.commit()
    title = contribution.title

    def change(session: Session) -> None:
        if contribution.kind == community.ITEM and contribution.cover_path:
            item = session.get(LibraryItem, contribution.source_id)
            if item is not None and item.cover_path == contribution.cover_path:
                item.cover_review = "rejected"
        _notify(session, "Not added to the Curiculy catalog",
                f'"{title}" wasn\'t added to the catalog for other families: {reason} '
                "Your own copy works just as before.")

    _tell_family(open_family, contribution.contributor, change)
    return ReviewResult(contribution=contribution_detail(catalog_db, contribution))


def ask(
    catalog_db: Session, contribution: CatalogContribution, question: str, *, admin: str, open_family: FamilyOpener
) -> ReviewResult:
    """Ask the family something; their next change brings it back to the queue."""
    _require_open(contribution)
    contribution.status = ASKED
    contribution.review_note = question
    contribution.reviewed_by = admin
    contribution.reviewed_at = func.now()
    catalog_db.commit()
    title = contribution.title
    where = "Curriculum planner" if contribution.kind == community.CURRICULUM else "Library"

    def change(session: Session) -> None:
        _notify(session, "A question about something you added",
                f'About "{title}": {question} Change it in your {where} and it comes back to us automatically.')

    _tell_family(open_family, contribution.contributor, change)
    return ReviewResult(contribution=contribution_detail(catalog_db, contribution))


def _resolve(catalog_db: Session, ref: dict) -> tuple[int | None, str]:
    """A curriculum item's catalog entry: 'ok', 'waiting' (still in review) or 'missing'."""
    if ref.get("entry_id"):
        return ref["entry_id"], "ok"
    if ref.get("contribution_id"):
        item = catalog_db.get(CatalogContribution, ref["contribution_id"])
        if item is not None and item.result_entry_id:
            return item.result_entry_id, "ok"
        if item is not None and item.status in OPEN_STATUSES:
            return None, "waiting"
    return None, "missing"


def _approve_curriculum(
    catalog_db: Session,
    contribution: CatalogContribution,
    request: ApproveRequest,
    *,
    admin: str,
    open_family: FamilyOpener,
) -> ReviewResult:
    data = contribution.data
    resolved: list[tuple[str, int]] = []
    waiting, left_out = [], []
    for ref in data.get("items") or []:
        entry_id, state = _resolve(catalog_db, ref)
        if state == "ok":
            resolved.append((ref["role"], entry_id))
        elif state == "waiting":
            waiting.append(ref["title"])
        else:
            left_out.append(ref["title"])
    if waiting:
        raise HTTPException(status_code=409, detail="Review its books first: " + ", ".join(waiting))
    textbooks = [entry_id for role, entry_id in resolved if role == "textbook"]
    if not textbooks:
        raise HTTPException(status_code=409, detail="Its textbook isn't in the catalog, so it can't be suggested.")

    signature = community.curriculum_signature(resolved)
    curriculum = catalog_db.scalars(
        select(CommunityCurriculum).where(CommunityCurriculum.signature == signature)
    ).first()
    edits = request.edits
    name = (edits.name if edits and edits.name else None) or data.get("name") or "Curriculum"
    if curriculum is None:
        textbook = catalog_db.get(CatalogEntry, textbooks[0])
        subject = data.get("subject_code") if data.get("subject_code") in SUBJECTS_BY_CODE else textbook.subject_code
        curriculum = CommunityCurriculum(
            name=name,
            subject_code=subject,
            grade=data.get("grade") or textbook.grade,
            days_per_week=data.get("days_per_week"),
            textbook_entry_id=textbook.id,
            signature=signature,
            families_count=1,
            status="published",
        )
        order = {"textbook": 0, "workbook": 1, "online": 2, "reading": 3, "teacher": 4}
        for position, (role, entry_id) in enumerate(sorted(set(resolved), key=lambda pair: (order.get(pair[0], 9), pair[1]))):
            curriculum.items.append(CommunityCurriculumItem(entry_id=entry_id, role=role, position=position))
        catalog_db.add(curriculum)
        status = APPROVED
    else:
        curriculum.families_count += 1
        if edits and edits.name:
            curriculum.name = edits.name
        status = MERGED
    catalog_db.flush()
    _close(contribution, status, admin, request.note)
    contribution.result_curriculum_id = curriculum.id
    catalog_db.commit()

    def change(session: Session) -> None:
        planned = session.get(PlannedCurriculum, contribution.source_id)
        if planned is not None:
            planned.community_curriculum_id = curriculum.id
        _notify(session, "Your curriculum helps other families",
                f'Thank you! Other families planning with the same textbook can now start from "{name}".')

    _tell_family(open_family, contribution.contributor, change)
    return ReviewResult(
        contribution=contribution_detail(catalog_db, contribution), curriculum_id=curriculum.id, left_out=left_out
    )


# --- Entries ------------------------------------------------------------------

def get_entry(catalog_db: Session, entry_id: int) -> CatalogEntry:
    entry = catalog_db.get(CatalogEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="No such catalog entry")
    return entry


def list_entries(catalog_db: Session, q: str | None, status: str | None, limit: int = 200):
    query = select(CatalogEntry)
    if status:
        query = query.where(CatalogEntry.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(CatalogEntry.title.ilike(pattern), CatalogEntry.isbn == (to_isbn13(q) or q)))
    rows = catalog_db.scalars(query.order_by(CatalogEntry.title, CatalogEntry.id).limit(limit))
    return [community.entry_summary(row) for row in rows]


def entry_admin_read(catalog_db: Session, entry: CatalogEntry) -> EntryAdminRead:
    base = community.entry_read(catalog_db, catalog_db, entry)
    return EntryAdminRead(
        **base.model_dump(),
        status=entry.status,
        versions=[
            EntryVersionRead(version=v.version, approved_by=v.approved_by, note=v.note,
                             contribution_id=v.contribution_id, created_at=v.created_at)
            for v in entry.versions
        ],
    )


def rollback(catalog_db: Session, entry: CatalogEntry, version: int, *, admin: str, note: str | None) -> EntryAdminRead:
    """Go back to an older version, as a new version (the history is kept)."""
    old = next((v for v in entry.versions if v.version == version), None)
    if old is None:
        raise HTTPException(status_code=404, detail="No such version")
    if version == entry.current_version:
        raise HTTPException(status_code=409, detail="That's already the current version.")
    add_version(catalog_db, entry, dict(old.data), admin=admin, note=note or f"Rolled back to version {version}")
    catalog_db.commit()
    return entry_admin_read(catalog_db, entry)


def set_status(catalog_db: Session, entry: CatalogEntry, status: str) -> EntryAdminRead:
    """Retire an entry (hidden from search; families keep their copies) or publish it again."""
    entry.status = status
    catalog_db.commit()
    return entry_admin_read(catalog_db, entry)

