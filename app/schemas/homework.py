from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import HomeworkHelpMessageRole, HomeworkHelpStatus, ParentNotificationType
from app.schemas.core import ORMModel


class HomeworkHelpMessageRead(ORMModel):
    id: int
    role: HomeworkHelpMessageRole
    content: str
    created_at: datetime


class HomeworkHelpSessionRead(ORMModel):
    id: int
    student_id: int
    assignment_id: int
    status: HomeworkHelpStatus
    push_count: int
    locked: bool = False
    messages: list[HomeworkHelpMessageRead] = Field(default_factory=list)


class HomeworkHelpSessionCreate(BaseModel):
    assignment_id: int


class HomeworkHelpMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class TutorReply(BaseModel):
    mode: str = "hint"
    message: str
    redirect: bool = False


class ParentNotificationRead(ORMModel):
    id: int
    type: ParentNotificationType
    student_id: int | None
    assignment_id: int | None
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


class ParentNotificationListRead(BaseModel):
    unread_count: int
    notifications: list[ParentNotificationRead]
