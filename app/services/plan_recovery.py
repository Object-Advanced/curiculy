"""Plans a restart left "processing" are marked failed at boot.

PDF and paper imports run in the app process after the request returns. If
the process stops mid-import, nothing finishes the plan: it stays
"processing", Edit and Apply stay disabled, and the SPA polls it forever.
Startup upkeep (``app.db_startup``) runs before the server accepts requests,
so no import can be running then; any plan still processing was interrupted.
The parent gets the usual "could not be processed" notification and can
upload again.

This assumes one app process, as today. Durable background jobs replace it.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import open_family_session
from app.enums import CurriculumPlanStatus
from app.models import CurriculumPlan
from app.services.notifications import notify_curriculum_plan_processed


def fail_interrupted_plans_for(session: Session) -> int:
    """Mark this family's processing plans failed and tell the parent; return how many."""
    plans = (
        session.query(CurriculumPlan)
        .filter(CurriculumPlan.status == CurriculumPlanStatus.PROCESSING)
        .all()
    )
    for plan in plans:
        plan.status = CurriculumPlanStatus.FAILED
        notify_curriculum_plan_processed(session, title=plan.title, ready=False)
    session.commit()
    return len(plans)


def fail_interrupted_plans(owner: Engine) -> int:
    """Do it for every family; return how many plans were marked failed.

    The owner role only finds which families have a processing plan; each
    family's update runs in its own family-scoped session.
    """
    with owner.connect() as conn:
        tenants = conn.execute(
            text("SELECT DISTINCT tenant_id FROM curriculum_plans WHERE status = :status"),
            {"status": CurriculumPlanStatus.PROCESSING.value},
        ).scalars().all()
    total = 0
    for tenant_id in tenants:
        session = open_family_session(tenant_id)
        try:
            total += fail_interrupted_plans_for(session)
        finally:
            session.close()
    return total
