"""Stuck? nudges: one nudge per lesson toward the family's own materials, then a grown-up."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_db
from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_catalog_db
from app.enums import HomeworkHelpMessageRole, HomeworkHelpStatus
from app.models import Assignment, HomeworkHelpMessage, HomeworkHelpSession, Student
from app.schemas.homework import (
    HomeworkHelpMessageCreate,
    HomeworkHelpMessageRead,
    HomeworkHelpOutcome,
    HomeworkHelpSessionCreate,
    HomeworkHelpSessionRead,
)
from app.services.assignments import AssignmentQuery
from app.services.child_accounts import is_child
from app.services.homework_help import (
    ANSWER_SEEKING_NUDGE,
    allow_another_nudge,
    first_name,
    has_nudge,
    is_answer_seeking,
    latest_session,
    notify_grown_up,
    notify_nudge,
    nudge_with_ollama,
    parent_note,
)

router = APIRouter(prefix="/homework-help", tags=["homework-help"])

ASK_A_GROWN_UP = "You've had your nudge on this one. Time to ask a grown-up."
GROWN_UP_MESSAGE = "Time to find a grown-up. We let them know you're stuck on this one."


def _session_read(session: HomeworkHelpSession) -> HomeworkHelpSessionRead:
    return HomeworkHelpSessionRead(
        id=session.id,
        student_id=session.student_id,
        assignment_id=session.assignment_id,
        status=session.status,
        push_count=session.push_count,
        locked=session.status == HomeworkHelpStatus.REDIRECTED,
        nudged=has_nudge(session),
        messages=[HomeworkHelpMessageRead.model_validate(item) for item in session.messages],
    )


def _own_assignment(user: CurrentUser, assignment: Assignment) -> None:
    if is_child(user) and assignment.student_id != user.student_id:
        raise HTTPException(status_code=404, detail="Assignment not found")


def _load_assignment(db: Session, assignment_id: int) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@router.get("/sessions", response_model=list[HomeworkHelpSessionRead])
def list_sessions(
    assignment_id: int = Query(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> list[HomeworkHelpSessionRead]:
    assignment = _load_assignment(db, assignment_id)
    _own_assignment(user, assignment)
    sessions = (
        db.query(HomeworkHelpSession)
        .filter(HomeworkHelpSession.assignment_id == assignment_id)
        .order_by(HomeworkHelpSession.id.desc())
        .all()
    )
    return [_session_read(session) for session in sessions]


@router.get("/sessions/{session_id}", response_model=HomeworkHelpSessionRead)
def get_session(
    session_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> HomeworkHelpSessionRead:
    session = db.get(HomeworkHelpSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    assignment = _load_assignment(db, session.assignment_id)
    _own_assignment(user, assignment)
    return _session_read(session)


def _child_session(db: Session, user: CurrentUser, session_id: int) -> HomeworkHelpSession:
    if not is_child(user):
        raise HTTPException(status_code=403, detail="Nudges are for students")
    session = db.get(HomeworkHelpSession, session_id)
    if session is None or session.student_id != user.student_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions", response_model=HomeworkHelpSessionRead, status_code=201)
def start_session(
    payload: HomeworkHelpSessionCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> HomeworkHelpSessionRead:
    """Open (or reopen) the child's nudge for a lesson. One per lesson until a parent resets it."""
    if not is_child(user):
        raise HTTPException(status_code=403, detail="Nudges are for students")
    assignment = _load_assignment(db, payload.assignment_id)
    _own_assignment(user, assignment)
    if user.student_id is None or db.get(Student, user.student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")

    latest = latest_session(db, assignment.id, user.student_id)
    if latest is not None and latest.status == HomeworkHelpStatus.REDIRECTED:
        raise HTTPException(status_code=403, detail=GROWN_UP_MESSAGE)
    if latest is not None and latest.status in (HomeworkHelpStatus.ACTIVE, HomeworkHelpStatus.HELPED):
        return _session_read(latest)

    session = HomeworkHelpSession(
        student_id=user.student_id,
        assignment_id=assignment.id,
        status=HomeworkHelpStatus.ACTIVE,
        push_count=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_read(session)


@router.post("/sessions/{session_id}/messages", response_model=HomeworkHelpSessionRead)
async def ask_for_nudge(
    session_id: int,
    payload: HomeworkHelpMessageCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
    catalog_db: Session = Depends(get_catalog_db),
) -> HomeworkHelpSessionRead:
    """The child says what's tricky (optional) and gets their one nudge."""
    session = _child_session(db, user, session_id)
    if session.status != HomeworkHelpStatus.ACTIVE or has_nudge(session):
        raise HTTPException(status_code=403, detail=ASK_A_GROWN_UP)
    assignment = _load_assignment(db, session.assignment_id)
    student = db.get(Student, session.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    content = payload.content.strip() or "I'm stuck."
    db.add(HomeworkHelpMessage(session_id=session.id, role=HomeworkHelpMessageRole.USER, content=content))
    if is_answer_seeking(content):
        session.push_count += 1
        nudge = ANSWER_SEEKING_NUDGE
    else:
        loaded = AssignmentQuery(db, catalog_db).get(assignment.id)
        nudge = await nudge_with_ollama(
            assignment_title=assignment.title,
            resource_title=loaded.resource_title if loaded else None,
            note=parent_note(assignment),
            child_name=first_name(student.name),
            user_message=content,
        )
    db.add(HomeworkHelpMessage(session_id=session.id, role=HomeworkHelpMessageRole.ASSISTANT, content=nudge))
    notify_nudge(db, student, assignment, nudge)
    db.commit()
    db.refresh(session)
    return _session_read(session)


@router.post("/sessions/{session_id}/outcome", response_model=HomeworkHelpSessionRead)
def record_outcome(
    session_id: int,
    payload: HomeworkHelpOutcome,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> HomeworkHelpSessionRead:
    """After the nudge: it helped, or go get a grown-up (which tells the parent)."""
    session = _child_session(db, user, session_id)
    assignment = _load_assignment(db, session.assignment_id)
    student = db.get(Student, session.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    if payload.outcome == "helped":
        if session.status != HomeworkHelpStatus.ACTIVE or not has_nudge(session):
            raise HTTPException(status_code=409, detail="There is no nudge to mark as helpful")
        session.status = HomeworkHelpStatus.HELPED
    else:
        if session.status not in (HomeworkHelpStatus.ACTIVE, HomeworkHelpStatus.HELPED):
            raise HTTPException(status_code=409, detail="A grown-up already knows")
        session.status = HomeworkHelpStatus.REDIRECTED
        db.add(
            HomeworkHelpMessage(
                session_id=session.id,
                role=HomeworkHelpMessageRole.SYSTEM,
                content=GROWN_UP_MESSAGE,
            )
        )
        notify_grown_up(db, student, assignment)
    db.commit()
    db.refresh(session)
    return _session_read(session)


@router.post("/assignments/{assignment_id}/unlock", response_model=list[HomeworkHelpSessionRead])
def unlock_help(
    assignment_id: int,
    _user: CurrentUser = Depends(require_parent),
    db: Session = Depends(get_tenant_db),
) -> list[HomeworkHelpSessionRead]:
    """A parent allows one more nudge on this lesson."""
    assignment = _load_assignment(db, assignment_id)
    allow_another_nudge(db, assignment.id)
    db.commit()
    sessions = (
        db.query(HomeworkHelpSession)
        .filter(HomeworkHelpSession.assignment_id == assignment.id)
        .order_by(HomeworkHelpSession.id.desc())
        .all()
    )
    return [_session_read(session) for session in sessions]
