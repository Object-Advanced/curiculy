from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import require_parent
from app.core.deps import get_tenant_db
from app.models import Curriculum, Enrollment, SchoolYear, Student
from app.schemas import EnrollmentCreate, EnrollmentRead

router = APIRouter(
    prefix="/enrollments",
    tags=["enrollments"],
    dependencies=[Depends(require_parent)],
)


@router.get("", response_model=list[EnrollmentRead])
def list_enrollments(tenant_db: Session = Depends(get_tenant_db)) -> list[Enrollment]:
    return tenant_db.query(Enrollment).order_by(Enrollment.id).all()


@router.get("/{enrollment_id}", response_model=EnrollmentRead)
def get_enrollment(
    enrollment_id: int, tenant_db: Session = Depends(get_tenant_db)
) -> Enrollment:
    enrollment = tenant_db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return enrollment


@router.post("", response_model=EnrollmentRead, status_code=201)
def create_enrollment(
    payload: EnrollmentCreate,
    tenant_db: Session = Depends(get_tenant_db),
) -> Enrollment:
    if tenant_db.get(Student, payload.student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")
    if tenant_db.get(Curriculum, payload.curriculum_id) is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    if tenant_db.get(SchoolYear, payload.school_year_id) is None:
        raise HTTPException(status_code=404, detail="School year not found")

    enrollment = Enrollment(**payload.model_dump())
    tenant_db.add(enrollment)
    try:
        tenant_db.commit()
    except IntegrityError:
        tenant_db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Student is already enrolled in this curriculum for this school year",
        ) from None
    tenant_db.refresh(enrollment)
    return enrollment
