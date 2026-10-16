"""The move engine: preview a move, then apply exactly what was previewed.

Moves: one lesson (push the rest back, or just this one), a day off or sick
day, a course's new days or a pause, and the catch-up sheet for a course that
has fallen behind. See ``app/services/moves.py``.
"""

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import require_parent
from app.schemas.moves import BehindCourse, CatchUpSheet, MoveApply, MovePreview, MoveRequest, MoveResult
from app.services import moves as service

router = APIRouter(prefix="/moves", tags=["moves"], dependencies=[Depends(require_parent)])


@router.post("/preview", response_model=MovePreview)
def preview_move(request: MoveRequest = Body(...), db: Session = Depends(get_tenant_db)) -> MovePreview:
    """What a move would change, and what it does to the family's guidelines. Saves nothing."""
    return service.preview(db, request)


@router.post("/apply", response_model=MoveResult)
def apply_move(payload: MoveApply, db: Session = Depends(get_tenant_db)) -> MoveResult:
    """Apply a previewed move. If the calendar changed since the preview, nothing is saved (409)."""
    return service.apply(db, payload.request, payload.plan_hash)


@router.get("/behind", response_model=list[BehindCourse])
def courses_behind(db: Session = Depends(get_tenant_db)) -> list[BehindCourse]:
    """Courses with lessons left on days that have passed."""
    return service.behind(db)


@router.get("/catch-up/{course_id}", response_model=CatchUpSheet)
def catch_up(
    course_id: int,
    allow_weekends: bool = Query(False),
    db: Session = Depends(get_tenant_db),
) -> CatchUpSheet:
    """How this course could catch up: each option with its result, one recommended."""
    return service.catch_up_sheet(db, course_id, allow_weekends)
