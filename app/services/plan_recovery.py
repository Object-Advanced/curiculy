"""Plans a restart left "processing" are marked failed at boot.

PDF and paper imports run in the app process after the request returns. If
the process stops mid-import, nothing finishes the plan: it stays
"processing", Edit and Apply stay disabled, and the SPA polls it forever.
Boot (init_databases) runs before the server accepts requests, so no import
can be running then; any plan still processing was interrupted. The parent
gets the usual "could not be processed" notification and can upload again.

This assumes one app process, as today. Durable background jobs replace it.
"""

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.enums import CurriculumPlanStatus
from app.models import CurriculumPlan
from app.services.notifications import notify_curriculum_plan_processed


def fail_interrupted_plans(engine: Engine) -> int:
    """Mark every processing plan in this household file failed; return how many."""
    with Session(engine) as session:
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
