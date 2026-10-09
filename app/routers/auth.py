"""Login, registration, demo tokens, student PIN logins, capture tokens, and user switching."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.rate_limit import enforce, limit_by_client
from app.core.security import (
    CurrentUser,
    get_current_user,
    hash_password,
    require_parent,
    verify_password,
)
from app.db import get_admin_db, open_tenant_session, provision_tenant
from app.core.deps import get_tenant_db
from app.enums import UserRole
from app.models import Student
from app.models.admin import InviteKey, User
from app.models.mixins import utcnow
from app.schemas.auth import (
    CaptureTokenIssued,
    CaptureTokenStatusRead,
    FamilyCodeRead,
    RegisterRequest,
    StudentHouseholdChildRead,
    StudentHouseholdRead,
    StudentHouseholdRequest,
    StudentTokenRequest,
    SwitchableUserRead,
    SwitchUserRequest,
    Token,
    TokenUserRead,
)
from app.services.capture_tokens import (
    active_capture_token,
    issue_capture_token,
    revoke_active_capture_tokens,
)
from app.services.child_accounts import (
    authenticate_child_pin,
    child_user_for_student,
    child_users_for_tenant,
    demo_token,
    is_child,
    parent_user_for_tenant,
    token_payload,
    verify_parent_password,
)
from app.services.family_codes import (
    display_code,
    family_code_for,
    rotate_family_code,
    sign_in_names,
    tenant_for_code,
)
from app.services.households import get_default_household

router = APIRouter(prefix="/auth", tags=["auth"])


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _unused_invite(admin_db: Session, key: str) -> InviteKey:
    invite = (
        admin_db.query(InviteKey)
        .filter(func.lower(InviteKey.key) == key.strip().lower())
        .one_or_none()
    )
    if invite is None or invite.redeemed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used invite key",
        )
    if invite.expires_at is not None and _as_utc(invite.expires_at) <= utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite key has expired",
        )
    return invite


def _token_user_read(user: CurrentUser, tenant_db: Session) -> TokenUserRead:
    display_name = "Parent"
    email = user.email
    if user.role == UserRole.CHILD.value:
        email = ""
        student = tenant_db.get(Student, user.student_id) if user.student_id else None
        display_name = student.name if student is not None else "Student"
    elif user.is_demo:
        display_name = "Demo"
    else:
        household = get_default_household(tenant_db)
        display_name = household.name if household is not None else (user.email or "Parent")
    return TokenUserRead(
        email=email,
        tenant_uuid=user.tenant_uuid,
        is_demo=user.is_demo,
        is_admin=user.is_admin,
        role=user.role or UserRole.PARENT.value,
        student_id=user.student_id,
        display_name=display_name,
    )


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_by_client("register", attempts=5, per_seconds=600))],
)
def register_user(
    payload: RegisterRequest,
    admin_db: Session = Depends(get_admin_db),
) -> Token:
    invite = _unused_invite(admin_db, payload.invite_key)
    existing = admin_db.query(User).filter(User.email == payload.email).one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    tenant_uuid = str(uuid4())
    provision_tenant(tenant_uuid)

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        tenant_uuid=tenant_uuid,
        is_admin=False,
        role=UserRole.PARENT.value,
    )
    invite.redeemed_at = utcnow()
    invite.tenant_uuid = tenant_uuid
    invite.email = payload.email
    admin_db.add(user)
    try:
        admin_db.commit()
    except IntegrityError as error:
        admin_db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from error
    admin_db.refresh(user)
    return token_payload(user)


@router.post(
    "/token",
    response_model=Token,
    dependencies=[Depends(limit_by_client("login", attempts=10, per_seconds=60))],
)
def login_for_access_token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    admin_db: Session = Depends(get_admin_db),
) -> Token:
    email = form.username.strip().lower()
    # Per account as well as per address, so spreading guesses across many
    # addresses does not get more tries at one parent's password.
    enforce(request, "login-account", email, attempts=20, per_seconds=900)
    user = admin_db.query(User).filter(User.email == email).one_or_none()
    if (
        user is None
        or user.role == UserRole.CHILD.value
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_payload(user)


@router.post(
    "/demo",
    response_model=Token,
    dependencies=[Depends(limit_by_client("demo", attempts=10, per_seconds=600))],
)
def demo_access_token() -> Token:
    return demo_token()


@router.get("/me", response_model=TokenUserRead)
def read_current_user(
    user: CurrentUser = Depends(get_current_user),
    tenant_db: Session = Depends(get_tenant_db),
) -> TokenUserRead:
    return _token_user_read(user, tenant_db)


@router.post(
    "/student-household",
    response_model=StudentHouseholdRead,
    dependencies=[Depends(limit_by_client("student-household", attempts=20, per_seconds=60))],
)
def list_student_household(
    payload: StudentHouseholdRequest,
    admin_db: Session = Depends(get_admin_db),
) -> StudentHouseholdRead:
    """First names of the children who can sign in, for a valid family code.

    Unauthenticated, so it answers only to the household's family code (not
    the parent's email) and shows first names only. Unknown codes get an
    empty list, the same as a household with no kid logins.
    """
    tenant_uuid = tenant_for_code(admin_db, payload.family_code)
    if tenant_uuid is None:
        return StudentHouseholdRead(students=[])
    login_ids = {
        row.student_id
        for row in child_users_for_tenant(admin_db, tenant_uuid)
        if row.student_id is not None
    }
    if not login_ids:
        return StudentHouseholdRead(students=[])
    tenant_db = open_tenant_session(tenant_uuid)
    try:
        names = {
            student.id: student.name
            for student in tenant_db.query(Student)
            .filter(Student.id.in_(login_ids))
            .order_by(Student.id)
            .all()
        }
    finally:
        tenant_db.close()
    shown = sign_in_names(names)
    return StudentHouseholdRead(
        students=[
            StudentHouseholdChildRead(student_id=student_id, name=shown[student_id])
            for student_id in names
        ]
    )


@router.post(
    "/student-token",
    response_model=Token,
    dependencies=[Depends(limit_by_client("student-token", attempts=20, per_seconds=60))],
)
def student_login(
    payload: StudentTokenRequest,
    admin_db: Session = Depends(get_admin_db),
) -> Token:
    tenant_uuid = tenant_for_code(admin_db, payload.family_code)
    child = (
        child_user_for_student(admin_db, tenant_uuid, payload.student_id)
        if tenant_uuid is not None
        else None
    )
    if child is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect name or PIN",
        )
    authenticate_child_pin(admin_db, child, payload.pin)
    return token_payload(child)


def _require_real_household(user: CurrentUser) -> None:
    if user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kid sign-in is not available in demo mode",
        )


@router.get("/family-code", response_model=FamilyCodeRead)
def read_family_code(
    user: CurrentUser = Depends(require_parent),
    admin_db: Session = Depends(get_admin_db),
) -> FamilyCodeRead:
    """The code a child enters once per device to find their name at sign-in."""
    _require_real_household(user)
    return FamilyCodeRead(code=display_code(family_code_for(admin_db, user.tenant_uuid).code))


@router.post("/family-code/rotate", response_model=FamilyCodeRead)
def rotate_household_family_code(
    user: CurrentUser = Depends(require_parent),
    admin_db: Session = Depends(get_admin_db),
) -> FamilyCodeRead:
    """Issue a new code. Devices that remembered the old one must enter the new one."""
    _require_real_household(user)
    return FamilyCodeRead(code=display_code(rotate_family_code(admin_db, user.tenant_uuid).code))


@router.get("/capture-token", response_model=CaptureTokenStatusRead)
def read_capture_token_status(
    user: CurrentUser = Depends(require_parent),
    admin_db: Session = Depends(get_admin_db),
) -> CaptureTokenStatusRead:
    if user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Capture tokens are not available in demo mode",
        )
    row = active_capture_token(admin_db, user.tenant_uuid)
    if row is None:
        return CaptureTokenStatusRead(active=False)
    return CaptureTokenStatusRead(
        active=True,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


@router.post("/capture-token", response_model=CaptureTokenIssued, status_code=status.HTTP_201_CREATED)
def create_capture_token(
    user: CurrentUser = Depends(require_parent),
    admin_db: Session = Depends(get_admin_db),
) -> CaptureTokenIssued:
    if user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Capture tokens are not available in demo mode",
        )
    token, row = issue_capture_token(
        admin_db,
        tenant_uuid=user.tenant_uuid,
        created_by_user_id=user.user_id,
    )
    return CaptureTokenIssued(
        access_token=token,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


@router.delete("/capture-token", response_model=CaptureTokenStatusRead)
def revoke_capture_token(
    user: CurrentUser = Depends(require_parent),
    admin_db: Session = Depends(get_admin_db),
) -> CaptureTokenStatusRead:
    if user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Capture tokens are not available in demo mode",
        )
    revoke_active_capture_tokens(admin_db, user.tenant_uuid)
    return CaptureTokenStatusRead(active=False)


@router.get("/switchable-users", response_model=list[SwitchableUserRead])
def list_switchable_users(
    user: CurrentUser = Depends(get_current_user),
    admin_db: Session = Depends(get_admin_db),
    tenant_db: Session = Depends(get_tenant_db),
) -> list[SwitchableUserRead]:
    household = get_default_household(tenant_db)
    parent_name = household.name if household is not None else "Parent"
    if user.is_demo:
        parent_name = "Demo"
    students = {student.id: student.name for student in tenant_db.query(Student).all()}
    login_ids = child_login_student_ids_safe(admin_db, user)
    rows = [
        SwitchableUserRead(
            kind="parent",
            display_name=parent_name,
            student_id=None,
            is_current=not is_child(user),
        )
    ]
    for student_id, name in students.items():
        if student_id not in login_ids and not user.is_demo:
            continue
        rows.append(
            SwitchableUserRead(
                kind="child",
                display_name=name,
                student_id=student_id,
                is_current=is_child(user) and user.student_id == student_id,
            )
        )
    return rows


def child_login_student_ids_safe(admin_db: Session, user: CurrentUser) -> set[int]:
    if user.is_demo:
        return set()
    return {row.student_id for row in child_users_for_tenant(admin_db, user.tenant_uuid) if row.student_id}


@router.post(
    "/switch",
    response_model=Token,
    dependencies=[Depends(limit_by_client("switch", attempts=10, per_seconds=60))],
)
def switch_user(
    payload: SwitchUserRequest,
    user: CurrentUser = Depends(get_current_user),
    admin_db: Session = Depends(get_admin_db),
    tenant_db: Session = Depends(get_tenant_db),
) -> Token:
    if payload.student_id is not None:
        student = tenant_db.get(Student, payload.student_id)
        if student is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    if is_child(user) and not user.is_demo:
        if not payload.parent_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Parent password required",
            )
        verify_parent_password(admin_db, user.tenant_uuid, payload.parent_password)

    if payload.student_id is None:
        if user.is_demo:
            return demo_token(jti=user.jti)
        parent = parent_user_for_tenant(admin_db, user.tenant_uuid)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent account not found",
            )
        return token_payload(parent)

    if user.is_demo:
        return demo_token(
            role=UserRole.CHILD.value,
            student_id=payload.student_id,
            jti=user.jti,
        )

    child = child_user_for_student(admin_db, user.tenant_uuid, payload.student_id)
    if child is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set a PIN for this student first",
        )
    return token_payload(child)
