"""Imports interrupted by a restart don't stay 'processing' forever."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import app.db as db_module
from app.config import settings
from app.db import TenantBase, init_databases
from app.enums import CurriculumPlanStatus, ParentNotificationType
from app.models import CurriculumPlan, ParentNotification
from app.services.plan_recovery import fail_interrupted_plans


def _household_file(path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{path}")
    TenantBase.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                CurriculumPlan(title="Abeka PDF", status=CurriculumPlanStatus.PROCESSING),
                CurriculumPlan(title="Paper Import", status=CurriculumPlanStatus.PROCESSING),
                CurriculumPlan(title="Finished guide", status=CurriculumPlanStatus.READY),
            ]
        )
        session.commit()
    return engine


def _statuses(engine: Engine) -> dict[str, CurriculumPlanStatus]:
    with Session(engine) as session:
        return {plan.title: plan.status for plan in session.query(CurriculumPlan).all()}


def test_processing_plans_are_failed_and_parents_told(tmp_path: Path) -> None:
    engine = _household_file(tmp_path / "tenant_family.db")
    try:
        assert fail_interrupted_plans(engine) == 2

        assert _statuses(engine) == {
            "Abeka PDF": CurriculumPlanStatus.FAILED,
            "Paper Import": CurriculumPlanStatus.FAILED,
            "Finished guide": CurriculumPlanStatus.READY,
        }
        with Session(engine) as session:
            notes = session.query(ParentNotification).all()
        assert [note.type for note in notes] == [ParentNotificationType.CURRICULUM_PLAN_FAILED] * 2
        assert "“Abeka PDF” could not be processed" in notes[0].body

        assert fail_interrupted_plans(engine) == 0
    finally:
        engine.dispose()


def test_boot_recovers_every_household_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("catalog", "tenant", "admin"):
        monkeypatch.setattr(settings, f"{name}_database_url", f"sqlite:///{tmp_path / name}.db")
    monkeypatch.setattr(db_module, "catalog_engine", create_engine(f"sqlite:///{tmp_path / 'catalog.db'}"))
    monkeypatch.setattr(db_module, "tenant_engine", create_engine(f"sqlite:///{tmp_path / 'tenant.db'}"))
    household = _household_file(tmp_path / "tenant_family.db")
    household.dispose()

    init_databases()

    engine = create_engine(f"sqlite:///{tmp_path / 'tenant_family.db'}")
    try:
        assert _statuses(engine)["Abeka PDF"] == CurriculumPlanStatus.FAILED
    finally:
        engine.dispose()
