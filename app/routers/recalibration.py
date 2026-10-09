"""Life Happens: inspect overdue work and shift the leftover schedule."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.models import Student
from app.schemas.recalibration import (
    RecalibrateExecuteRead,
    RecalibrateExecuteRequest,
    RecalibrateOptionsRead,
)
from app.services.recalibration import (
    RecalibrationError,
    calculate_recovery_options,
    execute_recalibration,
)

router = APIRouter(
    prefix="/recalibrate",
    tags=["recalibration"],
    dependencies=[Depends(require_parent)],
)


def _require_student(student_id: int, db: Session) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.get("/{student_id}/options", response_model=RecalibrateOptionsRead)
def recalibrate_options(
    student_id: int,
    db: Session = Depends(get_tenant_db),
) -> RecalibrateOptionsRead:
    """How many assignments are overdue, and how many days each strategy needs."""
    _require_student(student_id, db)
    try:
        return RecalibrateOptionsRead.model_validate(calculate_recovery_options(student_id, db))
    except RecalibrationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/{student_id}/execute", response_model=RecalibrateExecuteRead)
def recalibrate_execute(
    student_id: int,
    payload: RecalibrateExecuteRequest,
    db: Session = Depends(get_tenant_db),
) -> RecalibrateExecuteRead:
    """Shift every uncompleted assignment according to the chosen strategy."""
    _require_student(student_id, db)
    try:
        return RecalibrateExecuteRead.model_validate(
            execute_recalibration(student_id, payload.strategy, payload.options, db)
        )
    except RecalibrationError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(error)) from error
