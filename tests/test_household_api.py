"""Household identity: auto-create on first read, rename from the setup wizard."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Household
from app.schemas.core import household_letter
from app.services.households import DEFAULT_HOUSEHOLD_NAME


class TestHouseholdLetter:
    def test_skips_a_leading_the(self) -> None:
        assert household_letter("The Schroeder Family") == "S"
        assert household_letter("the Schroeder Family") == "S"
        assert household_letter("  THE   Schroeder  Family  ") == "S"

    def test_keeps_the_when_it_is_the_only_word(self) -> None:
        assert household_letter("The") == "T"

    def test_does_not_skip_theatre(self) -> None:
        assert household_letter("Theatre Kids") == "T"

    def test_uses_the_first_letter_otherwise(self) -> None:
        assert household_letter("Schroeder Family") == "S"
        assert household_letter("Default household") == "D"
        assert household_letter("") == "C"
        assert household_letter(None) == "C"


class TestHouseholdIdentity:
    def test_get_creates_the_default_household(self, client: TestClient, db: Session) -> None:
        response = client.get("/api/household")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == DEFAULT_HOUSEHOLD_NAME
        assert body["icon"] is None
        assert body["letter"] == "D"
        assert body["id"] >= 1
        stored = db.get(Household, body["id"])
        assert stored is not None
        assert stored.name == DEFAULT_HOUSEHOLD_NAME

    def test_patch_renames_the_household(self, client: TestClient, db: Session) -> None:
        created = client.get("/api/household").json()
        response = client.patch("/api/household", json={"name": "  The Rivera family  "})
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == created["id"]
        assert body["name"] == "The Rivera family"
        assert body["letter"] == "R"
        assert body["icon"] is None

        fetched = client.get("/api/household")
        assert fetched.json()["name"] == "The Rivera family"
        assert fetched.json()["letter"] == "R"
        stored = db.get(Household, created["id"])
        assert stored is not None
        assert stored.name == "The Rivera family"

    def test_patch_creates_the_row_when_none_exists(
        self, client: TestClient, db: Session
    ) -> None:
        assert db.query(Household).count() == 0
        response = client.patch("/api/household", json={"name": "Our Homeschool"})
        assert response.status_code == 200
        assert response.json()["name"] == "Our Homeschool"
        assert response.json()["letter"] == "O"
        assert db.query(Household).count() == 1

    def test_blank_name_is_rejected(self, client: TestClient) -> None:
        empty = client.patch("/api/household", json={"name": ""})
        assert empty.status_code == 422
        spaces = client.patch("/api/household", json={"name": "   "})
        assert spaces.status_code == 422
        missing = client.patch("/api/household", json={})
        assert missing.status_code == 422

    def test_auth_me_display_name_follows_the_rename(self, client: TestClient) -> None:
        client.patch("/api/household", json={"name": "The Smiths"})
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["display_name"] == "The Smiths"

    def test_patch_sets_a_school_icon(self, client: TestClient, db: Session) -> None:
        created = client.patch("/api/household", json={"name": "The Schroeder Family"}).json()
        response = client.patch("/api/household", json={"icon": "apple"})
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "The Schroeder Family"
        assert body["icon"] == "apple"
        assert body["letter"] == "S"
        stored = db.get(Household, created["id"])
        assert stored is not None
        assert stored.icon == "apple"

    def test_patch_letter_clears_the_icon(self, client: TestClient, db: Session) -> None:
        created = client.patch(
            "/api/household", json={"name": "The Schroeder Family", "icon": "books"}
        ).json()
        assert created["icon"] == "books"
        response = client.patch("/api/household", json={"icon": "letter"})
        assert response.status_code == 200
        assert response.json()["icon"] is None
        assert response.json()["letter"] == "S"
        stored = db.get(Household, created["id"])
        assert stored is not None
        assert stored.icon is None

    def test_unknown_icon_is_rejected(self, client: TestClient) -> None:
        client.get("/api/household")
        response = client.patch("/api/household", json={"icon": "dragon"})
        assert response.status_code == 422
