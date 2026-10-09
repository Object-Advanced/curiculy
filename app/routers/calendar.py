"""Household calendar: joint assignments shared across siblings.

The per-student calendar stays on the assignment routes. This one answers the
All Students view: only rows with a ``shared_group_uuid``, so private lessons
do not appear on the family board.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_catalog_db, get_tenant_db
from app.enums import CalendarPeriod
from app.schemas import AssignmentCalendarRead, AssignmentRead
from app.services.assignments import AssignmentQuery, InvalidDateRangeError, resolve_window
from app.services.clock import household_today

router = APIRouter(
    prefix="/calendar",
    tags=["calendar"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=AssignmentCalendarRead)
def list_shared_assignments(
    start_date: date | None = Query(
        default=None,
        description="Inclusive lower bound, or the date a 'period' is anchored on.",
    ),
    end_date: date | None = Query(
        default=None,
        description="Inclusive upper bound. Cannot be combined with 'period'.",
    ),
    period: CalendarPeriod | None = Query(
        default=None,
        description="Resolves to explicit bounds around 'start_date', or around "
        "today when no date is given. Weeks run Monday to Sunday.",
    ),
    tenant_db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> AssignmentCalendarRead:
    try:
        window = resolve_window(
            start_date=start_date,
            end_date=end_date,
            period=period,
            today=household_today(tenant_db),
        )
    except InvalidDateRangeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    assignments = AssignmentQuery(tenant_db, catalog_db).for_shared(window)
    return AssignmentCalendarRead(
        student_id=None,
        period=period,
        start_date=window.start_date,
        end_date=window.end_date,
        count=len(assignments),
        assignments=[AssignmentRead.model_validate(item) for item in assignments],
    )
