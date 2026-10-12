"""The community catalog: families' entries in, catalog entries out.

**In:** there's no share toggle. When a family's library item is ready to
schedule, its *structure* (details, chapters, the lesson list, an uploaded
cover) is contributed automatically and waits for an admin's review
(``item_changed``). Later edits refresh the open contribution. An item that
came from the catalog is only contributed when the family changes it: that's
a proposed correction. Curricula from the Curriculum planner are contributed
the same way once they're fully built (``curriculum_changed``).

**Never shared:** notes, login hints, the family's pace, schedules, progress,
children, work samples. The contributor is kept for review only.

**Out:** catalog entries show first in Library search; ``adopt_entry`` copies
one into a family's library; ``suggestions_for`` lists the curricula other
families built around a textbook.

Admin review lives in ``app.services.community_review``; the checks in
``app.services.community_checks``. See docs/6-planning/product-spine.md
("Community catalog").
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, object_session

from app.core.security import CurrentUser
from app.db import DEMO_TENANT_PREFIX, tenant_id_for
from app.evidence import resolve_evidence_file
from app.models import (
    BookEdition,
    CatalogContribution,
    CatalogEntry,
    CatalogEntryVersion,
    CatalogFlag,
    CommunityCurriculum,
    CommunityCurriculumItem,
    LibraryChapter,
    LibraryItem,
    LibraryLesson,
    PlannedCurriculum,
    Student,
)
from app.models.community import OPEN_STATUSES, PENDING, REJECTED, WITHDRAWN
from app.reference.subjects import subject_name
from app.schemas.library import CommunityLinkRead
from app.schemas.planner import ROLES
from app.schemas.community import (
    CommunityCurriculumRead,
    CommunityEntryRead,
    CommunityEntrySummary,
    SuggestedItem,
    SuggestionsRead,
)
from app.services import community_checks as checks
from app.services.library_rules import KINDS, TEXTBOOK, readiness
from app.utils.isbn import to_isbn13

logger = logging.getLogger(__name__)

NOTICE = (
    "The book details you enter (never anything about your family) help every family "
    "using the same book."
)
ITEM = "item"
CURRICULUM = "curriculum"

# The structure that's shared. Never: notes, login_note, usual_pages_per_day
# (the family's pace), or anything about the family.
ITEM_FIELDS = (
    "kind", "title", "author", "publisher", "series", "edition", "isbn", "subject_code", "grade",
    "reading_kind", "total_pages", "answer_key_start_page", "lesson_count", "measure",
    "minutes_per_session", "days_per_week", "consumable", "for_parent", "website_url",
)
CHAPTER_FIELDS = ("name", "start_page", "subject_code")
LESSON_FIELDS = ("number", "name", "type", "unit", "minutes", "start_page", "end_page")
COMMUNITY_COVER_PREFIX = "/api/community/entries/"


# --- Shared helpers -----------------------------------------------------------

def family_of(user: CurrentUser) -> str | None:
    """The family whose entries count as contributions; None for demo visitors."""
    if user.is_demo:
        return None
    family = tenant_id_for(user.tenant_uuid, user.jti)
    return None if family.startswith(DEMO_TENANT_PREFIX) else family


def data_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def title_key(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", title.lower()))[:255]


def snapshot_item(item: LibraryItem) -> dict:
    """What a family's item contributes: its structure, nothing about the family."""
    data = {name: getattr(item, name) for name in ITEM_FIELDS}
    data["isbn"] = to_isbn13(item.isbn) or item.isbn
    # A cover found by the lookup is shared; the catalog's own cover isn't
    # repeated, and an uploaded one travels separately (it's reviewed).
    lookup_cover = item.cover_url if item.cover_url and item.cover_url.startswith(("https://", "http://")) else None
    data["cover_url"] = lookup_cover
    data["chapters"] = [{name: getattr(chapter, name) for name in CHAPTER_FIELDS} for chapter in item.chapters]
    data["lessons"] = [{name: getattr(lesson, name) for name in LESSON_FIELDS} for lesson in item.lessons]
    return data


def current_version(catalog_db: Session, entry: CatalogEntry) -> CatalogEntryVersion:
    return catalog_db.scalars(
        select(CatalogEntryVersion).where(
            CatalogEntryVersion.entry_id == entry.id, CatalogEntryVersion.version == entry.current_version
        )
    ).one()


def _open(catalog_db: Session, family: str, kind: str, source_id: int) -> CatalogContribution | None:
    return catalog_db.scalars(
        select(CatalogContribution).where(
            CatalogContribution.contributor == family,
            CatalogContribution.kind == kind,
            CatalogContribution.source_id == source_id,
            CatalogContribution.status.in_(OPEN_STATUSES),
        )
    ).first()


def _withdraw(catalog_db: Session, family: str, kind: str, source_id: int) -> None:
    contribution = _open(catalog_db, family, kind, source_id)
    if contribution is not None:
        contribution.status = WITHDRAWN
        catalog_db.flush()


def describe_changes(old: dict, new: dict) -> str:
    """'title, total pages; 3 lessons changed': what a correction changes, in words."""
    fields = [
        name.replace("_", " ").replace("subject code", "subject")
        for name in sorted(set(old) | set(new))
        if name not in {"chapters", "lessons", "items"} and old.get(name) != new.get(name)
    ]
    parts = [", ".join(fields)] if fields else []
    for name, label in (("chapters", "chapter"), ("lessons", "lesson"), ("items", "item")):
        before, after = old.get(name) or [], new.get(name) or []
        if before == after:
            continue
        changed = sum(1 for a, b in zip(before, after) if a != b) + abs(len(before) - len(after))
        parts.append(f"{changed} {label}{'s' if changed != 1 else ''} changed")
    return "; ".join(parts) or "the cover"


# --- Contributing a library item ----------------------------------------------

def _cached_book(catalog_db: Session, isbn: str | None) -> checks.CachedBook | None:
    isbn13 = to_isbn13(isbn)
    if not isbn13:
        return None
    edition = catalog_db.scalars(select(BookEdition).where(BookEdition.isbn13 == isbn13)).first()
    if edition is None:
        return None
    return checks.CachedBook(
        title=edition.work.title,
        authors=[link.author_name for link in edition.work.authors],
        page_count=edition.page_count,
    )


def _contributor_facts(
    catalog_db: Session, family: str, started: datetime | None, lessons: int
) -> checks.ContributorFacts:
    def count(*conditions) -> int:
        return catalog_db.scalar(
            select(func.count()).select_from(CatalogContribution).where(
                CatalogContribution.contributor == family, *conditions
            )
        ) or 0

    accepted = count(CatalogContribution.status.in_(("approved", "merged")))
    rejected = count(CatalogContribution.status == REJECTED)
    last_hour = count(CatalogContribution.updated_at >= func.now() - timedelta(hours=1))
    seconds = None
    if started is not None:
        seconds = max(0.0, (datetime.now(timezone.utc) - started).total_seconds())
    return checks.ContributorFacts(accepted, rejected, last_hour, seconds, lessons)


def _agreement_facts(catalog_db: Session, contribution: CatalogContribution) -> checks.AgreementFacts:
    family, digest = contribution.contributor, contribution.data_hash
    others = select(CatalogContribution).where(
        CatalogContribution.contributor != family,
        CatalogContribution.kind == contribution.kind,
        CatalogContribution.status.notin_((WITHDRAWN, REJECTED)),
    )
    same_as_others = len({
        row.contributor for row in catalog_db.scalars(others.where(CatalogContribution.data_hash == digest))
    })

    others_agreeing = 0
    if contribution.isbn:
        groups: dict[str, set[str]] = {}
        for row in catalog_db.scalars(others.where(CatalogContribution.isbn == contribution.isbn)):
            if row.data_hash != digest:
                groups.setdefault(row.data_hash, set()).add(row.contributor)
        others_agreeing = max((len(families) for families in groups.values()), default=0)

    duplicate_of = None
    correction_of = None
    same_correction = 0
    if contribution.entry_id is not None:
        entry = catalog_db.get(CatalogEntry, contribution.entry_id)
        if entry is not None:
            version = current_version(catalog_db, entry)
            if version.data_hash != digest:
                correction_of = (entry.id, version.version, describe_changes(version.data, contribution.data))
                same_correction = len({
                    row.contributor for row in catalog_db.scalars(
                        others.where(
                            CatalogContribution.entry_id == entry.id,
                            CatalogContribution.data_hash == digest,
                            CatalogContribution.status.in_(OPEN_STATUSES),
                        )
                    )
                })
    elif contribution.kind == ITEM:
        duplicate = find_duplicate(catalog_db, contribution.data)
        if duplicate is not None:
            duplicate_of = (duplicate.id, duplicate.title)
    return checks.AgreementFacts(same_as_others, others_agreeing, duplicate_of, correction_of, same_correction)


def find_duplicate(catalog_db: Session, data: dict) -> CatalogEntry | None:
    """A published entry for the same book: the same ISBN, or the same title, publisher and edition."""
    published = select(CatalogEntry).where(CatalogEntry.status == "published", CatalogEntry.kind == data.get("kind"))
    isbn13 = to_isbn13(data.get("isbn"))
    if isbn13:
        found = catalog_db.scalars(published.where(CatalogEntry.isbn == isbn13)).first()
        if found is not None:
            return found
    if not data.get("title"):
        return None
    for entry in catalog_db.scalars(published.where(CatalogEntry.title_key == title_key(data["title"]))):
        same_publisher = (checks.normalize_publisher(entry.publisher) or "").lower() == (
            checks.normalize_publisher(data.get("publisher")) or ""
        ).lower()
        same_edition = (entry.edition or "").lower() == (data.get("edition") or "").lower()
        if same_publisher and same_edition:
            return entry
    return None


def _cover_reused_from(catalog_db: Session, image_hash: str | None) -> str | None:
    if not image_hash:
        return None
    entry = catalog_db.scalars(select(CatalogEntry).where(CatalogEntry.cover_hash == image_hash)).first()
    return entry.title if entry else None


def _store_flags(contribution: CatalogContribution, flags: list[checks.Flag]) -> None:
    contribution.flags.clear()
    for flag in flags:
        contribution.flags.append(
            CatalogFlag(code=flag.code, group=flag.group, level=flag.level, where=flag.where[:255], message=flag.message)
        )
    contribution.needs_review = any(flag.level == checks.REVIEW for flag in flags)


def _refresh(
    catalog_db: Session,
    *,
    family: str,
    kind: str,
    source_id: int,
    data: dict,
    item_kind: str | None,
    entry_id: int | None,
    based_on_version: int | None,
    cover_path: str | None = None,
) -> CatalogContribution:
    contribution = _open(catalog_db, family, kind, source_id)
    if contribution is None:
        contribution = CatalogContribution(contributor=family, kind=kind, source_id=source_id, status=PENDING)
        catalog_db.add(contribution)
    elif contribution.status != PENDING:
        # The family edited after an admin asked a question: back in the queue.
        contribution.status = PENDING
    contribution.item_kind = item_kind
    contribution.title = (data.get("title") or data.get("name") or "Untitled")[:255]
    contribution.isbn = to_isbn13(data.get("isbn")) if kind == ITEM else None
    contribution.entry_id = entry_id
    contribution.based_on_version = based_on_version
    contribution.data = data
    contribution.data_hash = data_hash(data)
    contribution.cover_path = cover_path
    contribution.cover_hash = None
    contribution.updated_at = func.now()
    catalog_db.flush()
    return contribution


def item_changed(db: Session, catalog_db: Session, item: LibraryItem, family: str | None) -> None:
    """Contribute (or refresh) the item's structure, once it's ready to schedule."""
    if family is None:
        return
    result = readiness(item)
    if not result.ready:
        # Not shared until it could be scheduled; an open contribution is now stale.
        _withdraw(catalog_db, family, ITEM, item.id)
        catalog_db.commit()
        return

    data = snapshot_item(item)
    digest = data_hash(data)
    cover = item.cover_path if item.cover_path and item.cover_review == "pending" else None
    entry = catalog_db.get(CatalogEntry, item.catalog_entry_id) if item.catalog_entry_id else None
    if entry is not None and not cover:
        unchanged = catalog_db.scalar(
            select(func.count()).select_from(CatalogEntryVersion).where(
                CatalogEntryVersion.entry_id == entry.id,
                CatalogEntryVersion.data_hash == digest,
                CatalogEntryVersion.version >= (item.catalog_version or entry.current_version),
            )
        )
        if unchanged:
            _withdraw(catalog_db, family, ITEM, item.id)
            catalog_db.commit()
            return

    contribution = _refresh(
        catalog_db,
        family=family,
        kind=ITEM,
        source_id=item.id,
        data=data,
        item_kind=item.kind,
        entry_id=entry.id if entry is not None else None,
        based_on_version=item.catalog_version if entry is not None else None,
        cover_path=cover,
    )

    fields = checks.text_fields(data)
    children = checks.first_names(list(db.scalars(select(Student.name))))
    flags = [
        *checks.structure_flags([(p.where, p.message) for p in result.problems if p.level == "check"]),
        *checks.identity_flags(data, _cached_book(catalog_db, data.get("isbn"))),
        *checks.publisher_flags(data),
        *checks.privacy_flags(fields, children),
        *checks.spam_flags(fields),
        *checks.copying_flags(data),
        *checks.link_flags(data),
    ]
    if cover:
        facts = None
        path = resolve_evidence_file(cover, tenant_uuid=cover.split("/", 1)[0])
        if path is not None:
            facts = checks.cover_facts(path)
        contribution.cover_hash = facts.image_hash if facts else None
        flags.extend(checks.cover_flags(facts, _cover_reused_from(catalog_db, contribution.cover_hash)))
    flags.extend(checks.agreement_flags(_agreement_facts(catalog_db, contribution)))
    flags.extend(checks.behavior_flags(
        _contributor_facts(catalog_db, family, item.created_at, len(item.lessons))
    ))
    _store_flags(contribution, flags)
    catalog_db.commit()


def item_removed(catalog_db: Session, item_id: int, family: str | None) -> None:
    """A deleted item's open contribution is withdrawn (published entries stay)."""
    if family is None:
        return
    _withdraw(catalog_db, family, ITEM, item_id)
    catalog_db.commit()


def safely(catalog_db: Session, action, *args) -> None:
    """Contributing never breaks the family's own save (it has already been
    saved); a failure is logged, and the family's next save tries again."""
    try:
        action(*args)
    except Exception:  # noqa: BLE001
        logger.exception("Could not update the community catalog contribution")
        catalog_db.rollback()


# --- Contributing a planned curriculum ----------------------------------------

def curriculum_signature(items: list[tuple[str, int]]) -> str:
    """'reading:77,textbook:12,workbook:40': a curriculum's exact make-up."""
    return ",".join(f"{role}:{entry_id}" for role, entry_id in sorted(set(items)))


def _item_ref(catalog_db: Session, family: str, link) -> dict:
    item = link.library_item
    ref = {"role": link.role, "kind": item.kind, "title": item.title, "entry_id": None, "contribution_id": None}
    if item.catalog_entry_id:
        ref["entry_id"] = item.catalog_entry_id
        return ref
    latest = catalog_db.scalars(
        select(CatalogContribution)
        .where(
            CatalogContribution.contributor == family,
            CatalogContribution.kind == ITEM,
            CatalogContribution.source_id == item.id,
            CatalogContribution.status != WITHDRAWN,
        )
        .order_by(CatalogContribution.id.desc())
    ).first()
    if latest is not None:
        ref["contribution_id"] = latest.id
        if latest.result_entry_id:
            ref["entry_id"] = latest.result_entry_id
    return ref


def curriculum_changed(
    db: Session, catalog_db: Session, curriculum: PlannedCurriculum, family: str | None, ready: bool
) -> None:
    """Contribute a fully built curriculum, so the next family can start from it."""
    if family is None:
        return
    if not ready:
        _withdraw(catalog_db, family, CURRICULUM, curriculum.id)
        catalog_db.commit()
        return
    refs = [_item_ref(catalog_db, family, link) for link in curriculum.items]
    data = {
        "name": curriculum.name,
        "subject_code": curriculum.subject_code,
        "grade": curriculum.grade,
        "days_per_week": curriculum.days_per_week,
        "items": refs,
    }
    if curriculum.community_curriculum_id and all(ref["entry_id"] for ref in refs):
        adopted = catalog_db.get(CommunityCurriculum, curriculum.community_curriculum_id)
        signature = curriculum_signature([(ref["role"], ref["entry_id"]) for ref in refs])
        if adopted is not None and adopted.signature == signature:
            _withdraw(catalog_db, family, CURRICULUM, curriculum.id)
            catalog_db.commit()
            return

    contribution = _refresh(
        catalog_db, family=family, kind=CURRICULUM, source_id=curriculum.id, data=data,
        item_kind=None, entry_id=None, based_on_version=None,
    )
    fields = [("Name", curriculum.name)]
    children = checks.first_names(list(db.scalars(select(Student.name))))
    flags = [*checks.privacy_flags(fields, children), *checks.spam_flags(fields)]
    waiting = [ref["title"] for ref in refs if not ref["entry_id"] and ref["contribution_id"]]
    if waiting:
        flags.append(checks.Flag("items_waiting", "structure", checks.NOTE, "Items",
                                 f"Waiting for {len(waiting)} of its books to be reviewed: {', '.join(waiting[:5])}."))
    missing = [ref["title"] for ref in refs if not ref["entry_id"] and not ref["contribution_id"]]
    if missing:
        flags.append(checks.Flag("items_missing", "structure", checks.REVIEW, "Items",
                                 f"Not in the catalog and not contributed: {', '.join(missing[:5])}. "
                                 "Approving leaves them out."))
    flags.extend(checks.agreement_flags(_agreement_facts(catalog_db, contribution)))
    flags.extend(checks.behavior_flags(_contributor_facts(catalog_db, family, None, 0)))
    _store_flags(contribution, flags)
    catalog_db.commit()


def curriculum_removed(catalog_db: Session, curriculum_id: int, family: str | None) -> None:
    if family is None:
        return
    _withdraw(catalog_db, family, CURRICULUM, curriculum_id)
    catalog_db.commit()


# --- Reading the catalog (families) ------------------------------------------

def entry_cover_url(entry: CatalogEntry) -> str | None:
    if entry.cover_path:
        return f"{COMMUNITY_COVER_PREFIX}{entry.id}/cover"
    return entry.cover_url


def entry_detail_line(entry: CatalogEntry) -> str:
    """'170 lessons' / '12 chapters, 220 pages' / '1 family'."""
    parts = []
    if entry.lessons_count:
        parts.append(f"{entry.lessons_count} lessons")
    if entry.chapters_count:
        parts.append(f"{entry.chapters_count} chapters")
    if entry.total_pages:
        parts.append(f"{entry.total_pages} pages")
    families = "1 family" if entry.families_count == 1 else f"{entry.families_count} families"
    parts.append(f"entered by {families}")
    return ", ".join(parts)


def entry_summary(entry: CatalogEntry) -> CommunityEntrySummary:
    return CommunityEntrySummary(
        id=entry.id,
        kind=entry.kind,
        kind_label=KINDS.get(entry.kind, entry.kind),
        title=entry.title,
        author=entry.author,
        publisher=entry.publisher,
        edition=entry.edition,
        isbn=entry.isbn,
        subject_code=entry.subject_code,
        subject_name=subject_name(entry.subject_code),
        grade=entry.grade,
        total_pages=entry.total_pages,
        chapters_count=entry.chapters_count,
        lessons_count=entry.lessons_count,
        cover_url=entry_cover_url(entry),
        families_count=entry.families_count,
        detail=entry_detail_line(entry),
    )


def get_published_entry(catalog_db: Session, entry_id: int) -> CatalogEntry:
    entry = catalog_db.get(CatalogEntry, entry_id)
    if entry is None or entry.status != "published":
        raise HTTPException(status_code=404, detail="Not in the Curiculy catalog")
    return entry


def _your_copy(db: Session, entry: CatalogEntry) -> LibraryItem | None:
    return db.scalars(
        select(LibraryItem).where(LibraryItem.catalog_entry_id == entry.id).order_by(LibraryItem.id)
    ).first()


def entry_read(db: Session, catalog_db: Session, entry: CatalogEntry) -> CommunityEntryRead:
    data = current_version(catalog_db, entry).data
    mine = _your_copy(db, entry)
    return CommunityEntryRead(
        **entry_summary(entry).model_dump(),
        version=entry.current_version,
        **{name: data.get(name) for name in (
            "series", "reading_kind", "answer_key_start_page", "lesson_count", "measure",
            "minutes_per_session", "days_per_week", "website_url",
        )},
        for_parent=bool(data.get("for_parent")),
        chapters=data.get("chapters") or [],
        lessons=data.get("lessons") or [],
        in_curricula=catalog_db.scalar(
            select(func.count(func.distinct(CommunityCurriculumItem.curriculum_id)))
            .join(CommunityCurriculum, CommunityCurriculum.id == CommunityCurriculumItem.curriculum_id)
            .where(CommunityCurriculumItem.entry_id == entry.id, CommunityCurriculum.status == "published")
        ) or 0,
        library_item_id=mine.id if mine else None,
    )


def search_entries(catalog_db: Session, text: str, isbn13: str | None, limit: int = 6) -> list[CatalogEntry]:
    published = select(CatalogEntry).where(CatalogEntry.status == "published")
    if isbn13:
        return list(catalog_db.scalars(published.where(CatalogEntry.isbn == isbn13).limit(limit)))
    pattern = f"%{text}%"
    return list(catalog_db.scalars(
        published.where(
            or_(
                CatalogEntry.title.ilike(pattern),
                CatalogEntry.author.ilike(pattern),
                CatalogEntry.publisher.ilike(pattern),
                CatalogEntry.title_key.contains(title_key(text)),
            )
        )
        .order_by(CatalogEntry.families_count.desc(), CatalogEntry.title)
        .limit(limit)
    ))


def adopt_entry(
    db: Session, catalog_db: Session, entry: CatalogEntry, *, counted: bool = True
) -> tuple[LibraryItem, bool]:
    """Copy a catalog entry into the family's library (or return the copy it has).
    ``counted`` is False for demo visitors, who don't add to "used by N families"."""
    mine = _your_copy(db, entry)
    if mine is not None:
        return mine, False
    data = current_version(catalog_db, entry).data
    item = LibraryItem(**{name: data.get(name) for name in ITEM_FIELDS if name not in {"consumable", "for_parent"}})
    item.consumable = bool(data.get("consumable"))
    item.for_parent = bool(data.get("for_parent"))
    item.cover_url = entry_cover_url(entry)
    item.catalog_entry_id = entry.id
    item.catalog_version = entry.current_version
    for position, chapter in enumerate(data.get("chapters") or []):
        item.chapters.append(LibraryChapter(position=position, **{k: chapter.get(k) for k in CHAPTER_FIELDS}))
    for position, lesson in enumerate(data.get("lessons") or []):
        fields = {k: lesson.get(k) for k in LESSON_FIELDS}
        fields["type"] = fields["type"] or "lesson"
        item.lessons.append(LibraryLesson(position=position, **fields))
    db.add(item)
    db.commit()
    if counted:
        entry.families_count += 1
        catalog_db.commit()
    return item, True


def link_status(item: LibraryItem, ready: bool) -> CommunityLinkRead:
    """How the item relates to the community catalog, in plain words."""
    session = object_session(item)
    in_review = session.scalar(
        select(func.count()).select_from(CatalogContribution).where(
            CatalogContribution.kind == ITEM,
            CatalogContribution.source_id == item.id,
            CatalogContribution.contributor == func.curiculy_current_tenant(),
            CatalogContribution.status.in_(OPEN_STATUSES),
        )
    )
    entry = session.get(CatalogEntry, item.catalog_entry_id) if item.catalog_entry_id else None
    if in_review:
        return CommunityLinkRead(
            status="in_review",
            label="Shared with the Curiculy catalog. An admin reviews it before other families see it.",
            entry_id=entry.id if entry else None,
            families_count=entry.families_count if entry else None,
        )
    if entry is not None:
        families = "1 family" if entry.families_count == 1 else f"{entry.families_count} families"
        return CommunityLinkRead(
            status="in_catalog",
            label=f"In the Curiculy catalog, used by {families}.",
            entry_id=entry.id,
            families_count=entry.families_count,
        )
    if not ready:
        return CommunityLinkRead(
            status="not_shared",
            label="Shared with the Curiculy catalog once it's ready to schedule. " + NOTICE,
        )
    return CommunityLinkRead(status="not_shared", label="Not in the Curiculy catalog.")


# --- Curricula other families built (suggestions) -----------------------------

def textbook_entry_for(catalog_db: Session, item: LibraryItem) -> CatalogEntry | None:
    if item.catalog_entry_id:
        return catalog_db.get(CatalogEntry, item.catalog_entry_id)
    isbn13 = to_isbn13(item.isbn)
    if not isbn13:
        return None
    return catalog_db.scalars(
        select(CatalogEntry).where(
            CatalogEntry.isbn == isbn13, CatalogEntry.kind == TEXTBOOK, CatalogEntry.status == "published"
        )
    ).first()


def _yours_by_entry(db: Session, entry_ids: set[int]) -> dict[int, int]:
    if not entry_ids:
        return {}
    rows = db.execute(
        select(LibraryItem.catalog_entry_id, LibraryItem.id).where(LibraryItem.catalog_entry_id.in_(entry_ids))
    ).all()
    found: dict[int, int] = {}
    for entry_id, item_id in rows:
        found.setdefault(entry_id, item_id)
    return found


def suggestions_for(db: Session, catalog_db: Session, item: LibraryItem) -> SuggestionsRead:
    entry = textbook_entry_for(catalog_db, item)
    if entry is None or item.kind != TEXTBOOK:
        return SuggestionsRead(textbook=None, families_count=0, curricula=[], often_used_with=[],
                               message="No other family has built a curriculum with this textbook yet. "
                                       "Build yours, and it will help the next family.")
    curricula = list(catalog_db.scalars(
        select(CommunityCurriculum)
        .where(CommunityCurriculum.textbook_entry_id == entry.id, CommunityCurriculum.status == "published")
        .order_by(CommunityCurriculum.families_count.desc(), CommunityCurriculum.id)
    ))
    entry_ids = {link.entry_id for curriculum in curricula for link in curriculum.items}
    yours = _yours_by_entry(db, entry_ids)

    def suggested(link, families: int) -> SuggestedItem:
        return SuggestedItem(
            role=link.role, role_label=ROLES.get(link.role, link.role), entry=entry_summary(link.entry),
            library_item_id=yours.get(link.entry_id), families_count=families,
        )

    total = sum(curriculum.families_count for curriculum in curricula)
    usage: dict[tuple[str, int], int] = {}
    links: dict[tuple[str, int], object] = {}
    for curriculum in curricula:
        for link in curriculum.items:
            if link.entry_id == entry.id and link.role == "textbook":
                continue
            key = (link.role, link.entry_id)
            usage[key] = usage.get(key, 0) + curriculum.families_count
            links[key] = link
    often = sorted(usage, key=lambda key: (-usage[key], links[key].entry.title))
    families = "1 family" if total == 1 else f"{total} families"
    return SuggestionsRead(
        textbook=entry_summary(entry),
        families_count=total,
        curricula=[
            CommunityCurriculumRead(
                id=curriculum.id,
                name=curriculum.name,
                subject_code=curriculum.subject_code,
                subject_name=subject_name(curriculum.subject_code),
                grade=curriculum.grade,
                days_per_week=curriculum.days_per_week,
                families_count=curriculum.families_count,
                items=[suggested(link, curriculum.families_count) for link in curriculum.items],
            )
            for curriculum in curricula
        ],
        often_used_with=[suggested(links[key], usage[key]) for key in often],
        message=(
            f"{families} built a curriculum around {entry.title}. Start from theirs and change "
            "anything (other families pick different books all the time), or build your own."
            if curricula else
            "No other family has built a curriculum with this textbook yet. Build yours, and it will help the next family."
        ),
    )
