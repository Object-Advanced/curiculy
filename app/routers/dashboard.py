"""Family dashboard analytics: today's progress and a seven-day completion trend.

Status is the completion signal; ``completion_date`` is often null because the
checklist only patches status. Totals and daily buckets therefore use
``scheduled_date``.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.db import get_tenant_db
from app.enums import AssignmentStatus
from app.models import Assignment, Student
from app.schemas import DashboardStatsRead, StudentTodayProgress, StudentWeeklyTrend

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_parent)],
)


@router.get("/stats", response_model=DashboardStatsRead)
def get_dashboard_stats(db: Session = Depends(get_tenant_db)) -> DashboardStatsRead:
    """Return today's assignment progress and completed work for the last 7 days."""
    today = date.today()
    trend_dates = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    students = db.query(Student).order_by(Student.id).all()
    student_ids = {student.id for student in students}

    today_totals: dict[int, int] = {student.id: 0 for student in students}
    today_completed: dict[int, int] = {student.id: 0 for student in students}
    for student_id, status in db.query(Assignment.student_id, Assignment.status).filter(
        Assignment.scheduled_date == today
    ):
        if student_id not in student_ids:
            continue
        today_totals[student_id] += 1
        if status == AssignmentStatus.COMPLETED:
            today_completed[student_id] += 1

    week_start = trend_dates[0]
    week_counts: dict[int, dict[date, int]] = {student.id: {} for student in students}
    for student_id, scheduled_date in db.query(
        Assignment.student_id, Assignment.scheduled_date
    ).filter(
        Assignment.status == AssignmentStatus.COMPLETED,
        Assignment.scheduled_date >= week_start,
        Assignment.scheduled_date <= today,
    ):
        if student_id not in student_ids:
            continue
        day_counts = week_counts[student_id]
        day_counts[scheduled_date] = day_counts.get(scheduled_date, 0) + 1

    return DashboardStatsRead(
        today=today,
        today_progress=[
            StudentTodayProgress(
                student_id=student.id,
                name=student.name,
                color_hex=student.color_hex,
                total=today_totals[student.id],
                completed=today_completed[student.id],
            )
            for student in students
        ],
        trend_dates=trend_dates,
        weekly_trend=[
            StudentWeeklyTrend(
                student_id=student.id,
                name=student.name,
                color_hex=student.color_hex,
                completed=[week_counts[student.id].get(day, 0) for day in trend_dates],
            )
            for student in students
        ],
    )
