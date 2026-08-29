"""Homework helper sessions for a child's own assignments."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user, require_parent
from app.db import get_tenant_db
from app.enums import HomeworkHelpMessageRole, HomeworkHelpStatus, UserRole
from app.models import Assignment, HomeworkHelpMessage, HomeworkHelpSession, Student
from app.schemas.homework import (
    HomeworkHelpMessageCreate,
    HomeworkHelpMessageRead,
    HomeworkHelpSessionCreate,
    HomeworkHelpSessionRead,
)
from app.services.child_accounts import is_child
from app.services.homework_help import (
    PUSH_LIMIT,
    append_assignment_note,
    assignment_is_locked,
    is_answer_seeking,
    notify_help_redirect,
    notify_help_started,
    tutor_with_ollama,
    unlock_assignment,
)

router = APIRouter(prefix="/homework-help", tags=["homework-help"])


def _session_read(session: HomeworkHelpSession) -> HomeworkHelpSessionRead:
    return HomeworkHelpSessionRead(
        id=session.id,
        student_id=session.student_id,
        assignment_id=session.assignment_id,
        status=session.status,
        push_count=session.push_count,
        locked=session.status == HomeworkHelpStatus.REDIRECTED,
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


@router.post("/sessions", response_model=HomeworkHelpSessionRead, status_code=201)
def start_session(
    payload: HomeworkHelpSessionCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> HomeworkHelpSessionRead:
    if not is_child(user):
        raise HTTPException(status_code=403, detail="Homework help is for students")
    assignment = _load_assignment(db, payload.assignment_id)
    _own_assignment(user, assignment)
    student_id = user.student_id
    if student_id is None:
        raise HTTPException(status_code=400, detail="Student not found")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    if assignment_is_locked(db, assignment.id):
        raise HTTPException(
            status_code=403,
            detail="Homework help is locked until a parent allows it again",
        )

    active = (
        db.query(HomeworkHelpSession)
        .filter(
            HomeworkHelpSession.assignment_id == assignment.id,
            HomeworkHelpSession.student_id == student.id,
            HomeworkHelpSession.status == HomeworkHelpStatus.ACTIVE,
        )
        .order_by(HomeworkHelpSession.id.desc())
        .first()
    )
    if active is not None:
        return _session_read(active)

    session = HomeworkHelpSession(
        student_id=student.id,
        assignment_id=assignment.id,
        status=HomeworkHelpStatus.ACTIVE,
        push_count=0,
    )
    db.add(session)
    append_assignment_note(assignment, f"{student.name} started help on “{assignment.title}”.")
    notify_help_started(db, student, assignment)
    db.commit()
    db.refresh(session)
    return _session_read(session)


@router.post("/sessions/{session_id}/messages", response_model=HomeworkHelpSessionRead)
async def post_message(
    session_id: int,
    payload: HomeworkHelpMessageCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
) -> HomeworkHelpSessionRead:
    if not is_child(user):
        raise HTTPException(status_code=403, detail="Homework help is for students")
    session = db.get(HomeworkHelpSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    assignment = _load_assignment(db, session.assignment_id)
    _own_assignment(user, assignment)
    if user.role == UserRole.CHILD.value and session.student_id != user.student_id:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != HomeworkHelpStatus.ACTIVE:
        raise HTTPException(
            status_code=403,
            detail="Ask a parent for help. Homework help is paused on this assignment.",
        )

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    student = db.get(Student, session.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    user_message = HomeworkHelpMessage(
        session_id=session.id,
        role=HomeworkHelpMessageRole.USER,
        content=content,
    )
    db.add(user_message)
    db.flush()

    history = list(session.messages)
    if user_message not in history:
        history.append(user_message)

    redirected = False
    if is_answer_seeking(content):
        session.push_count += 1
        if session.push_count >= PUSH_LIMIT:
            redirected = True

    if not redirected:
        reply = await tutor_with_ollama(
            assignment_title=assignment.title,
            student_name=student.name,
            history=history,
            user_message=content,
        )
        if reply.redirect:
            redirected = True
            assistant_text = reply.message.strip() or (
                "Please ask a parent for help with this. I'm pausing homework help now."
            )
        else:
            assistant_text = reply.message.strip() or (
                "Try a similar example with different numbers, then come back to yours."
            )
        db.add(
            HomeworkHelpMessage(
                session_id=session.id,
                role=HomeworkHelpMessageRole.ASSISTANT,
                content=assistant_text,
            )
        )

    if redirected:
        session.status = HomeworkHelpStatus.REDIRECTED
        redirect_text = (
            "Please ask a parent for help. I'm pausing homework help on this assignment."
        )
        db.add(
            HomeworkHelpMessage(
                session_id=session.id,
                role=HomeworkHelpMessageRole.SYSTEM,
                content=redirect_text,
            )
        )
        append_assignment_note(
            assignment,
            f"{student.name} was redirected to a parent on “{assignment.title}”.",
        )
        notify_help_redirect(db, student, assignment)

    db.commit()
    db.refresh(session)
    return _session_read(session)


@router.post("/assignments/{assignment_id}/unlock", response_model=list[HomeworkHelpSessionRead])
def unlock_help(
    assignment_id: int,
    _user: CurrentUser = Depends(require_parent),
    db: Session = Depends(get_tenant_db),
) -> list[HomeworkHelpSessionRead]:
    assignment = _load_assignment(db, assignment_id)
    unlock_assignment(db, assignment.id)
    append_assignment_note(assignment, "A parent allowed homework help again.")
    db.commit()
    sessions = (
        db.query(HomeworkHelpSession)
        .filter(HomeworkHelpSession.assignment_id == assignment.id)
        .order_by(HomeworkHelpSession.id.desc())
        .all()
    )
    return [_session_read(session) for session in sessions]
