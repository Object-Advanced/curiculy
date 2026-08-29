from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.core import ORMModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    tenant_uuid: str
    is_demo: bool = False
    is_admin: bool = False
    role: str = "parent"
    student_id: int | None = None
    display_name: str = ""


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    invite_key: str = Field(min_length=1, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        local, _, domain = email.partition("@")
        if not local or "." not in domain:
            raise ValueError("Enter a valid email address")
        return email

    @field_validator("invite_key")
    @classmethod
    def normalize_invite_key(cls, value: str) -> str:
        key = value.strip()
        if not key:
            raise ValueError("Invite key is required")
        return key


class InviteKeyRead(ORMModel):
    id: int
    key: str
    created_at: datetime
    expires_at: datetime | None = None


class StudentHouseholdRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class StudentHouseholdChildRead(BaseModel):
    student_id: int
    name: str


class StudentHouseholdRead(BaseModel):
    students: list[StudentHouseholdChildRead]


class StudentTokenRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    student_id: int
    pin: str = Field(min_length=4, max_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class StudentPinUpsert(BaseModel):
    pin: str = Field(min_length=4, max_length=8)


class SwitchableUserRead(BaseModel):
    kind: str
    display_name: str
    student_id: int | None = None
    is_current: bool = False


class SwitchUserRequest(BaseModel):
    student_id: int | None = None
    parent_password: str | None = None
