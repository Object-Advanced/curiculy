"""The community catalog: automatic contributions, the checks, and admin review."""

from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import CurrentUser, require_admin
from app.db import set_tenant
from app.enums import ParentNotificationType
from app.models import (
    CatalogContribution,
    CatalogEntry,
    LibraryChapter,
    LibraryItem,
    ParentNotification,
    Student,
)
from app.routers.community_admin import get_family_opener
from app.routers.library import get_book_providers
from app.services import community
from app.services import community_checks as checks
from app.services.households import get_default_household
from tests.conftest import TEST_TENANT, session_like

BOOK = {
    "kind": "reading_book", "title": "Charlotte's Web", "author": "E. B. White",
    "total_pages": 184, "isbn": "9780064400558",
}


@pytest.fixture
def admin(client: TestClient, db: Session) -> TestClient:
    """The same client, allowed into the admin review queue."""

    @contextmanager
    def open_family(family: str):
        db.flush()
        set_tenant(db.connection(), family)
        session = session_like(db)
        try:
            yield session
        finally:
            session.close()
            set_tenant(db.connection(), TEST_TENANT)

    client.app.dependency_overrides[require_admin] = lambda: CurrentUser(
        email="admin@curiculy.test", tenant_uuid=TEST_TENANT, is_admin=True
    )
    client.app.dependency_overrides[get_family_opener] = lambda: open_family

    async def no_lookups():
        yield []

    client.app.dependency_overrides[get_book_providers] = no_lookups
    return client


def _add(client: TestClient, **fields) -> dict:
    response = client.post("/api/library", json={**BOOK, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def _open(db: Session, source_id: int | None = None) -> list[CatalogContribution]:
    query = select(CatalogContribution).where(CatalogContribution.status.in_(("pending", "asked")))
    if source_id is not None:
        query = query.where(CatalogContribution.source_id == source_id)
    return list(db.scalars(query.order_by(CatalogContribution.id)))


def _codes(contribution: CatalogContribution | dict) -> set[str]:
    flags = contribution["flags"] if isinstance(contribution, dict) else contribution.flags
    return {flag["code"] if isinstance(flag, dict) else flag.code for flag in flags}


def _contribute_as(db: Session, as_family, family: str, chapters: int = 2, **fields) -> int:
    """Another family adds a ready book (its contribution goes to the queue)."""
    as_family(family)
    item = LibraryItem(**{**BOOK, **fields})
    for index in range(chapters):
        item.chapters.append(LibraryChapter(position=index, name=f"Chapter {index + 1}", start_page=1 + index * 20))
    db.add(item)
    db.flush()
    item_id = item.id  # read it now: back in the test family, row-level security hides it
    community.item_changed(db, db, item, family)
    as_family(TEST_TENANT)
    return _open(db, item_id)[0].id


def _approve(admin: TestClient, contribution_id: int, **body) -> dict:
    response = admin.post(f"/api/admin/community/contributions/{contribution_id}/approve", json=body)
    assert response.status_code == 200, response.text
    return response.json()


class TestContributing:
    def test_a_ready_item_is_contributed_automatically(self, client: TestClient, db: Session) -> None:
        item = _add(client)
        assert item["community"]["status"] == "in_review"
        [contribution] = _open(db)
        assert (contribution.contributor, contribution.kind, contribution.item_kind) == (TEST_TENANT, "item", "reading_book")
        assert contribution.data["title"] == "Charlotte's Web" and contribution.isbn == "9780064400558"

    def test_an_unfinished_item_waits_until_it_is_ready(self, client: TestClient, db: Session) -> None:
        item = _add(client, kind="workbook", title="Spectrum Math 3", author=None)
        assert _open(db) == []
        assert "once it's ready to schedule" in item["community"]["label"]
        client.patch(f"/api/library/{item['id']}", json={"subject_code": "math", "grade": "3"})
        done = client.put(f"/api/library/{item['id']}/chapters", json=[{"name": "Addition", "start_page": 5}]).json()
        assert done["community"]["status"] == "in_review" and len(_open(db)) == 1
        client.put(f"/api/library/{item['id']}/chapters", json=[])  # unfinished again
        assert _open(db) == []

    def test_edits_refresh_the_same_contribution(self, client: TestClient, db: Session) -> None:
        item = _add(client)
        client.patch(f"/api/library/{item['id']}", json={"title": "Charlotte's Web (Anniversary)"})
        [contribution] = _open(db)
        assert contribution.title == "Charlotte's Web (Anniversary)"

    def test_nothing_about_the_family_is_shared(self, client: TestClient, db: Session) -> None:
        _add(client, kind="online_program", title="IXL Math", author=None, total_pages=None, isbn=None,
             website_url="https://www.ixl.com/math", subject_code="math", grade="3", measure="minutes",
             minutes_per_session=20, days_per_week=4, login_note="Log in as Ada", notes="Ada loves the badges",
             usual_pages_per_day=3)
        [contribution] = _open(db)
        for private in ("login_note", "notes", "usual_pages_per_day", "cover_path", "cover_review"):
            assert private not in contribution.data
        assert "Ada" not in str(contribution.data)

    def test_deleting_withdraws_it(self, client: TestClient, db: Session) -> None:
        item = _add(client)
        client.delete(f"/api/library/{item['id']}")
        assert _open(db) == []
        assert db.scalars(select(CatalogContribution)).one().status == "withdrawn"

    def test_demo_visitors_dont_contribute(self) -> None:
        demo = CurrentUser(email="demo@curiculy.com", tenant_uuid="DEMO", jti="abc", is_demo=True)
        assert community.family_of(demo) is None
        assert community.family_of(CurrentUser(email="a@b.c", tenant_uuid="fam-1")) == "fam-1"

    def test_a_childs_name_is_flagged_without_repeating_it(self, client: TestClient, db: Session) -> None:
        db.add(Student(household_id=get_default_household(db).id, name="Ada Lovelace"))
        db.flush()
        _add(client, title="Ada's Big Book of Reading", isbn=None)
        [contribution] = _open(db)
        [flag] = [flag for flag in contribution.flags if flag.code == "child_name"]
        assert flag.level == "review" and "Ada" not in flag.message
        assert contribution.needs_review is True

    def test_a_failure_never_breaks_the_familys_save(self, client: TestClient, db: Session) -> None:
        with patch("app.services.community.item_changed", side_effect=RuntimeError("catalog down")):
            item = _add(client)
        assert client.get(f"/api/library/{item['id']}").status_code == 200


class TestChecks:
    def test_links(self) -> None:
        assert checks.link_flags({"website_url": "https://www.ixl.com/math"}) == []
        assert checks.link_flags({"website_url": "https://learn.k12.oh.us/x"}) == []
        assert [f.code for f in checks.link_flags({"website_url": "http://www.ixl.com"})] == ["not_https"]
        assert [f.code for f in checks.link_flags({"website_url": "https://bit.ly/abc"})] == ["shortener"]
        assert [f.code for f in checks.link_flags({"website_url": "https://free-prizes.example"})] == ["unknown_site"]
        personal = checks.link_flags({"website_url": "https://www.ixl.com/signin/smithfamily"})
        assert [(f.code, f.group) for f in personal] == [("personal_link", "privacy")]
        assert [f.code for f in checks.link_flags({"website_url": "https://www.khanacademy.org/join/ABC123"})] == ["personal_link"]

    def test_identity(self) -> None:
        assert [f.code for f in checks.identity_flags({"isbn": "9780064400559"}, None)] == ["isbn_checksum"]
        cached = checks.CachedBook(title="Charlotte's Web", authors=["E. B. White"], page_count=184)
        assert checks.identity_flags({"title": "Charlotte's Web", "author": "White", "total_pages": 190}, cached) == []
        flags = checks.identity_flags({"title": "Stuart Little", "author": "Someone", "total_pages": 250}, cached)
        assert {(f.code, f.level) for f in flags} == {
            ("isbn_title", "review"), ("isbn_author", "note"), ("pages_off", "review")
        }

    def test_spam(self) -> None:
        fields = [("Title", "FREE SHIPPING TODAY"), ("Chapter 1", "visit www.example.com"), ("Lesson 2", "shit")]
        assert {f.code for f in checks.spam_flags(fields)} == {"all_caps", "link_in_text", "profanity"}
        assert checks.spam_flags([("Title", "Dick and Jane"), ("Title", "Saxon Math 5/4")]) == []

    def test_privacy(self) -> None:
        fields = [("Chapter 1", "Email me at mom@example.com"), ("Chapter 2", "Call 555-123-4567"),
                  ("Chapter 3", "We live at 1234 Maple Street"), ("Chapter 4", "Lesson 3 Down the Road")]
        assert {f.where for f in checks.privacy_flags(fields, [])} == {"Chapter 1", "Chapter 2", "Chapter 3"}
        assert checks.first_names(["Ada Lovelace", "Bo", "  "]) == ["ada"]

    def test_copying(self) -> None:
        long_name = "Read aloud the following passage to your student and then " * 3
        [flag] = checks.copying_flags({"lessons": [{"number": 7, "name": long_name}]})
        assert flag.where == "Lesson 7" and "copyright" in flag.message

    def test_publisher_names(self) -> None:
        assert checks.normalize_publisher("Bob Jones University Press") == "BJU Press"
        assert checks.normalize_publisher("Abeka Book, Inc.") == "Abeka"
        assert checks.normalize_publisher("Houghton Mifflin") == "Houghton Mifflin"

    def test_covers(self, tmp_path: Path) -> None:
        blank = tmp_path / "blank.webp"
        Image.new("RGB", (120, 150), (250, 250, 250)).save(blank, format="WEBP")
        facts = checks.cover_facts(blank)
        codes = {f.code for f in checks.cover_flags(facts, "Holes")}
        assert codes == {"cover_uploaded", "cover_small", "cover_blank", "cover_reused"}
        assert checks.cover_facts(tmp_path / "missing.webp") is None


class TestReview:
    def test_admins_only(self, client: TestClient) -> None:
        assert client.get("/api/admin/community/contributions").status_code == 403

    def test_approving_publishes_it_and_thanks_the_family(self, admin: TestClient, db: Session) -> None:
        item = _add(admin)
        [summary] = admin.get("/api/admin/community/contributions").json()
        assert summary["contributor_label"].startswith("Family ") and TEST_TENANT not in summary["contributor_label"]
        detail = admin.get(f"/api/admin/community/contributions/{summary['id']}").json()
        assert "first_time" in _codes(detail) and detail["data"]["title"] == "Charlotte's Web"

        result = _approve(admin, summary["id"])
        entry = db.get(CatalogEntry, result["entry_id"])
        assert (entry.title, entry.current_version, entry.families_count) == ("Charlotte's Web", 1, 1)
        assert result["contribution"]["status"] == "approved"
        mine = admin.get(f"/api/library/{item['id']}").json()
        assert mine["community"]["status"] == "in_catalog" and mine["community"]["entry_id"] == entry.id
        note = db.scalars(select(ParentNotification)).one()
        assert note.type == ParentNotificationType.CATALOG_UPDATE and "Thank you" in note.body
        assert admin.post(f"/api/admin/community/contributions/{summary['id']}/approve", json={}).status_code == 409

    def test_approve_with_edits(self, admin: TestClient, db: Session) -> None:
        _add(admin, publisher="Bob Jones University Press", title="CHARLOTTE'S WEB")
        [contribution] = _open(db)
        assert "all_caps" in _codes(contribution) and "publisher_name" in _codes(contribution)
        result = _approve(admin, contribution.id, edits={"title": "Charlotte's Web"})
        entry = db.get(CatalogEntry, result["entry_id"])
        assert (entry.title, entry.publisher) == ("Charlotte's Web", "BJU Press")

    def test_families_find_it_and_add_it_in_seconds(self, admin: TestClient, db: Session, as_family) -> None:
        entry_id = _approve(admin, _contribute_as(db, as_family, "other", chapters=3))["entry_id"]
        found = admin.get("/api/library/search", params={"q": "charlotte"}).json()["results"]
        assert found[0]["source"] == "community" and found[0]["catalog_entry_id"] == entry_id
        assert found[0]["detail"] == "3 chapters, 184 pages, entered by 1 family"
        preview = admin.get(f"/api/community/entries/{entry_id}").json()
        assert [c["name"] for c in preview["chapters"]] == ["Chapter 1", "Chapter 2", "Chapter 3"]
        assert preview["library_item_id"] is None

        added = admin.post("/api/library/from-community", json={"entry_id": entry_id})
        assert added.status_code == 201
        copy = added.json()
        assert (copy["ready"], len(copy["chapters"]), copy["community"]["status"]) == (True, 3, "in_catalog")
        assert copy["community"]["families_count"] == 2
        assert _open(db) == []  # an unchanged copy isn't contributed again
        again = admin.post("/api/library/from-community", json={"entry_id": entry_id})
        assert again.status_code == 200 and again.json()["id"] == copy["id"]

    def test_changing_a_catalog_copy_proposes_a_correction(self, admin: TestClient, db: Session, as_family) -> None:
        entry_id = _approve(admin, _contribute_as(db, as_family, "other"))["entry_id"]
        copy = admin.post("/api/library/from-community", json={"entry_id": entry_id}).json()
        admin.patch(f"/api/library/{copy['id']}", json={"total_pages": 192})
        [correction] = _open(db, copy["id"])
        assert correction.entry_id == entry_id and "correction" in _codes(correction)
        detail = admin.get(f"/api/admin/community/contributions/{correction.id}").json()
        assert detail["is_correction"] is True
        assert [(c["field"], c["catalog"], c["contributed"]) for c in detail["changes"]["fields"]] == [
            ("total_pages", 184, 192)
        ]
        _approve(admin, correction.id)
        entry = admin.get(f"/api/admin/community/entries/{entry_id}").json()
        assert (entry["version"], entry["total_pages"]) == (2, 192)

        rolled = admin.post(f"/api/admin/community/entries/{entry_id}/rollback", json={"version": 1}).json()
        assert (rolled["version"], rolled["total_pages"]) == (3, 184)
        assert [v["version"] for v in rolled["versions"]] == [1, 2, 3]

    def test_rejecting_tells_the_family_and_keeps_their_copy(self, admin: TestClient, db: Session) -> None:
        item = _add(admin)
        [contribution] = _open(db)
        response = admin.post(f"/api/admin/community/contributions/{contribution.id}/reject",
                              json={"reason": "This edition's pages don't match."})
        assert response.json()["contribution"]["status"] == "rejected"
        note = db.scalars(select(ParentNotification)).one()
        assert "pages don't match" in note.body and "Your own copy works" in note.body
        assert admin.get(f"/api/library/{item['id']}").json()["community"]["status"] == "not_shared"

    def test_asking_the_family_and_their_edit_answers(self, admin: TestClient, db: Session) -> None:
        item = _add(admin)
        [contribution] = _open(db)
        admin.post(f"/api/admin/community/contributions/{contribution.id}/ask",
                   json={"question": "Is this the 1952 edition?"})
        db.refresh(contribution)
        assert contribution.status == "asked"
        assert "1952 edition" in db.scalars(select(ParentNotification)).one().body
        admin.patch(f"/api/library/{item['id']}", json={"edition": "1952"})
        db.refresh(contribution)
        assert (contribution.status, contribution.data["edition"]) == ("pending", "1952")

    def test_the_same_book_again_is_a_merge_candidate(self, admin: TestClient, db: Session, as_family) -> None:
        entry_id = _approve(admin, _contribute_as(db, as_family, "other"))["entry_id"]
        item = _add(admin, total_pages=186)
        [contribution] = _open(db, item["id"])
        assert "duplicate" in _codes(contribution)
        detail = admin.get(f"/api/admin/community/contributions/{contribution.id}").json()
        assert detail["compare_entry"]["id"] == entry_id
        merged = admin.post(f"/api/admin/community/contributions/{contribution.id}/merge",
                            json={"entry_id": entry_id}).json()
        assert merged["contribution"]["status"] == "merged"
        assert db.get(CatalogEntry, entry_id).families_count == 2
        assert admin.get(f"/api/library/{item['id']}").json()["community"]["entry_id"] == entry_id

    def test_families_who_agree_are_noted(self, admin: TestClient, db: Session, as_family) -> None:
        _contribute_as(db, as_family, "other", chapters=0)
        _add(admin)
        [mine] = [c for c in _open(db) if c.contributor == TEST_TENANT]
        assert "agrees" in _codes(mine)

    def test_retired_entries_leave_search(self, admin: TestClient, db: Session, as_family) -> None:
        entry_id = _approve(admin, _contribute_as(db, as_family, "other"))["entry_id"]
        admin.post(f"/api/admin/community/entries/{entry_id}/retire")
        found = admin.get("/api/library/search", params={"q": "charlotte"}).json()["results"]
        assert all(result["source"] != "community" for result in found)
        assert admin.get(f"/api/community/entries/{entry_id}").status_code == 404

    def test_uploaded_covers_are_reviewed(
        self, admin: TestClient, db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "evidence_dir", tmp_path)
        item = _add(admin)
        buffer = BytesIO()
        cover = Image.new("RGB", (600, 900), (40, 90, 160))
        cover.paste((240, 200, 40), (100, 100, 500, 400))
        cover.save(buffer, format="PNG")
        admin.post(f"/api/library/{item['id']}/cover", files={"file": ("cover.png", buffer.getvalue(), "image/png")})
        [contribution] = _open(db)
        assert "cover_uploaded" in _codes(contribution) and "cover_blank" not in _codes(contribution)
        assert admin.get(f"/api/admin/community/contributions/{contribution.id}/cover").status_code == 200

        entry_id = _approve(admin, contribution.id)["entry_id"]
        image = admin.get(f"/api/community/entries/{entry_id}/cover")
        assert image.status_code == 200 and image.headers["content-type"] == "image/webp"
        assert admin.get(f"/api/library/{item['id']}").json()["cover"]["review"] == "approved"
