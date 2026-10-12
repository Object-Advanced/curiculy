"""The database keeps families apart, and the migrations match the models.

These run against the real migrated database as the app's own role, so they
prove the row-level security that production relies on.
"""

from __future__ import annotations

from datetime import date

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.config import reveal_secret, settings
from app.db import (
    TenantSession,
    app_engine,
    open_family_session,
    open_shared_session,
    owner_engine,
    tenant_id_for,
)
from app.db_safety import (
    _object_problems,
    _reference_problems,
    _table_problems,
    database_safety_problems,
)
from app.models import Assignment, Household, Student
from app.services.family_data import family_tables
from migrations.metadata import include_object, target_metadata

pytestmark = pytest.mark.usefixtures("committed_db")


def _family(tenant_id: str, child: str) -> tuple[int, int]:
    """Make a household with one child as ``tenant_id``; return (household id, student id)."""
    session = open_family_session(tenant_id)
    try:
        household = Household(name=f"{child} family")
        session.add(household)
        session.flush()
        student = Student(household_id=household.id, name=child)
        session.add(student)
        session.commit()
        return household.id, student.id
    finally:
        session.close()


class TestMigrations:
    def test_migrations_match_the_models(self) -> None:
        with owner_engine().connect() as conn:
            context = MigrationContext.configure(
                conn, opts={"include_object": include_object, "compare_type": True}
            )
            assert compare_metadata(context, target_metadata) == []

    def test_safety_check_passes_on_the_migrated_database(self) -> None:
        assert database_safety_problems(app_engine()) == []


class TestSafetyCheckCatchesMistakes:
    """Each mistake is made inside a transaction that is rolled back."""

    def _problems_after(self, ddl: list[str]) -> list[str]:
        with owner_engine().connect() as conn:
            transaction = conn.begin()
            try:
                for statement in ddl:
                    conn.execute(text(statement))
                return [*_table_problems(conn), *_reference_problems(conn), *_object_problems(conn)]
            finally:
                transaction.rollback()

    def test_table_that_is_neither_family_nor_shared(self) -> None:
        problems = self._problems_after(["CREATE TABLE stray (id int primary key)"])
        assert any("stray" in problem and "not a known shared table" in problem for problem in problems)

    def test_family_table_without_row_level_security(self) -> None:
        problems = self._problems_after(["ALTER TABLE students DISABLE ROW LEVEL SECURITY"])
        assert any("students" in problem and "row-level security is off" in problem for problem in problems)

    def test_family_table_not_forced(self) -> None:
        problems = self._problems_after(["ALTER TABLE students NO FORCE ROW LEVEL SECURITY"])
        assert any("students" in problem and "not forced" in problem for problem in problems)

    def test_family_table_without_a_policy(self) -> None:
        problems = self._problems_after(["DROP POLICY family_isolation ON students"])
        assert any("students" in problem and "no policy" in problem for problem in problems)

    def test_reference_that_ignores_the_family(self) -> None:
        problems = self._problems_after(
            ["ALTER TABLE assignments DROP CONSTRAINT fk_tenant_assignments_student_id"]
        )
        assert any("assignments(student_id) -> students" in problem for problem in problems)

    def test_views_and_security_definer_functions(self) -> None:
        problems = self._problems_after(
            [
                "CREATE VIEW all_students AS SELECT * FROM students",
                "CREATE FUNCTION peek() RETURNS int LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'",
            ]
        )
        assert any("all_students" in problem for problem in problems)
        assert any("peek" in problem for problem in problems)

    def test_app_role_cannot_bypass_and_owns_nothing(self) -> None:
        with app_engine().connect() as conn:
            row = conn.execute(
                text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).one()
        assert (row.rolsuper, row.rolbypassrls) == (False, False)


class TestRowLevelSecurity:
    def test_a_family_sees_only_its_own_rows(self) -> None:
        _family("family-a", "Ada")
        _family("family-b", "Ben")
        for tenant_id, name in (("family-a", "Ada"), ("family-b", "Ben")):
            session = open_family_session(tenant_id)
            try:
                assert [s.name for s in session.query(Student).all()] == [name]
                assert session.query(Household).count() == 1
            finally:
                session.close()

    def test_no_family_set_means_no_rows_and_no_inserts(self) -> None:
        _family("family-a", "Ada")
        session = open_shared_session()
        try:
            for table in family_tables():
                assert session.execute(select(func.count()).select_from(table)).scalar() == 0
            session.add(Household(name="Nobody's"))
            with pytest.raises(DBAPIError):  # refused by the policy (or the NOT NULL)
                session.commit()
        finally:
            session.close()

    def test_cannot_change_or_delete_another_familys_rows(self) -> None:
        _, ada = _family("family-a", "Ada")
        _family("family-b", "Ben")
        session = open_family_session("family-b")
        try:
            assert session.execute(
                text("UPDATE students SET name = 'Hacked' WHERE id = :id"), {"id": ada}
            ).rowcount == 0
            assert session.execute(text("DELETE FROM students WHERE id = :id"), {"id": ada}).rowcount == 0
            session.commit()
        finally:
            session.close()
        session = open_family_session("family-a")
        try:
            assert session.get(Student, ada).name == "Ada"
        finally:
            session.close()

    def test_cannot_write_a_row_for_another_family(self) -> None:
        household, _ = _family("family-a", "Ada")
        session = open_family_session("family-b")
        try:
            session.add(Student(household_id=household, name="Sneaky", tenant_id="family-a"))
            with pytest.raises(DBAPIError):
                session.commit()
        finally:
            session.close()

    def test_cannot_point_at_another_familys_row(self) -> None:
        _, ada = _family("family-a", "Ada")
        _family("family-b", "Ben")
        session = open_family_session("family-b")
        try:
            session.add(Assignment(student_id=ada, title="Borrowed", scheduled_date=date(2026, 10, 12)))
            with pytest.raises(IntegrityError):
                session.commit()
        finally:
            session.close()

    def test_the_family_ends_with_the_transaction(self) -> None:
        """A pooled connection never carries one request's family into the next."""
        _family("family-a", "Ada")
        one_connection = create_engine(
            reveal_secret(settings.database_url), pool_size=1, max_overflow=0
        )
        try:
            session = TenantSession(bind=one_connection, tenant_id="family-a")
            try:
                assert session.query(Student).count() == 1
                session.commit()
            finally:
                session.close()
            with one_connection.connect() as conn:  # the same pooled connection
                assert conn.execute(text("SELECT curiculy_current_tenant()")).scalar() is None
                assert conn.execute(text("SELECT count(*) FROM students")).scalar() == 0
        finally:
            one_connection.dispose()

    def test_interleaved_sessions_stay_apart(self) -> None:
        _family("family-a", "Ada")
        _family("family-b", "Ben")
        a = open_family_session("family-a")
        b = open_family_session("family-b")
        try:
            for _ in range(3):
                assert [s.name for s in a.query(Student).all()] == ["Ada"]
                assert [s.name for s in b.query(Student).all()] == ["Ben"]
                a.commit()
                b.commit()
        finally:
            a.close()
            b.close()

    def test_turning_row_security_off_is_refused_not_obeyed(self) -> None:
        _family("family-a", "Ada")
        with app_engine().connect() as conn:
            conn.execute(text("SET row_security = off"))
            with pytest.raises(DBAPIError):
                conn.execute(text("SELECT count(*) FROM students"))


class TestTenantIds:
    def test_each_demo_token_gets_its_own_family(self) -> None:
        first = tenant_id_for("DEMO", "jti-1")
        second = tenant_id_for("DEMO", "jti-2")
        assert first != second
        assert first.startswith("demo-") and second.startswith("demo-")

    def test_a_real_family_cannot_claim_a_demo_id(self) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException):
            tenant_id_for("demo-0123")

    def test_tenant_session_scopes_every_transaction(self) -> None:
        session = TenantSession(bind=app_engine(), tenant_id="family-a")
        try:
            assert session.execute(text("SELECT curiculy_current_tenant()")).scalar() == "family-a"
            session.commit()
            assert session.execute(text("SELECT curiculy_current_tenant()")).scalar() == "family-a"
        finally:
            session.close()


def test_owner_role_sees_every_family_for_upkeep() -> None:
    _family("family-a", "Ada")
    _family("family-b", "Ben")
    with Session(owner_engine()) as session:
        assert session.query(Student).count() == 2
