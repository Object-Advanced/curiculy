"""Imports interrupted by a restart don't stay 'processing' forever."""

import pytest

from app.db import open_family_session, owner_engine
from app.enums import CurriculumPlanStatus, ParentNotificationType
from app.models import CurriculumPlan, ParentNotification
from app.services.plan_recovery import fail_interrupted_plans

pytestmark = pytest.mark.usefixtures("committed_db")


def _plans(tenant_id: str, *plans: tuple[str, CurriculumPlanStatus]) -> None:
    session = open_family_session(tenant_id)
    try:
        session.add_all(CurriculumPlan(title=title, status=status) for title, status in plans)
        session.commit()
    finally:
        session.close()


def _statuses(tenant_id: str) -> dict[str, CurriculumPlanStatus]:
    session = open_family_session(tenant_id)
    try:
        return {plan.title: plan.status for plan in session.query(CurriculumPlan).all()}
    finally:
        session.close()


def test_processing_plans_are_failed_and_parents_told() -> None:
    _plans(
        "family-a",
        ("Abeka PDF", CurriculumPlanStatus.PROCESSING),
        ("Paper Import", CurriculumPlanStatus.PROCESSING),
        ("Finished guide", CurriculumPlanStatus.READY),
    )

    assert fail_interrupted_plans(owner_engine()) == 2

    assert _statuses("family-a") == {
        "Abeka PDF": CurriculumPlanStatus.FAILED,
        "Paper Import": CurriculumPlanStatus.FAILED,
        "Finished guide": CurriculumPlanStatus.READY,
    }
    session = open_family_session("family-a")
    try:
        notes = session.query(ParentNotification).order_by(ParentNotification.id).all()
    finally:
        session.close()
    assert [note.type for note in notes] == [ParentNotificationType.CURRICULUM_PLAN_FAILED] * 2
    assert "“Abeka PDF” could not be processed" in notes[0].body

    assert fail_interrupted_plans(owner_engine()) == 0


def test_every_family_is_recovered_and_told_only_about_its_own() -> None:
    _plans("family-a", ("A's guide", CurriculumPlanStatus.PROCESSING))
    _plans("family-b", ("B's guide", CurriculumPlanStatus.PROCESSING))

    assert fail_interrupted_plans(owner_engine()) == 2

    for tenant_id, title in (("family-a", "A's guide"), ("family-b", "B's guide")):
        assert _statuses(tenant_id) == {title: CurriculumPlanStatus.FAILED}
        session = open_family_session(tenant_id)
        try:
            bodies = [note.body for note in session.query(ParentNotification).all()]
        finally:
            session.close()
        assert len(bodies) == 1 and title in bodies[0]
