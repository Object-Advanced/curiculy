from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import settings, validate_runtime_configuration
from app.core.middleware import (
    BodySizeLimitMiddleware,
    SecurityHeadersMiddleware,
    SelectiveGZipMiddleware,
)
from app.core.rate_limit import RateLimiter
from app.evidence import EvidenceRejected, evidence_root
from app.routers import (
    admin,
    assignments,
    attendance,
    auth,
    books,
    calendar,
    catalog,
    curricula,
    curriculum_plans,
    dashboard,
    enrollments,
    evidence,
    exceptions,
    health,
    household,
    homework_help,
    notifications,
    pacing,
    portfolios,
    recalibration,
    reports,
    school_years,
    settings as settings_routes,
    students,
)


class StaticRevalidateMiddleware(BaseHTTPMiddleware):
    """Tell CDNs and browsers to revalidate /static so UI edits are not stuck for hours."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_runtime_configuration()
    evidence_root()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Curiculy",
        description="Homeschool curriculum pacing, family calendar, and compliance foundation.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.rate_limiter = RateLimiter()
    # The last one added runs first: the size cap refuses oversized uploads
    # before anything else, then headers, compression, and static caching.
    application.add_middleware(StaticRevalidateMiddleware)
    application.add_middleware(SelectiveGZipMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        BodySizeLimitMiddleware, max_bytes=settings.max_upload_megabytes * 1024 * 1024
    )

    @application.exception_handler(EvidenceRejected)
    async def evidence_rejected(_request: Request, error: EvidenceRejected) -> JSONResponse:
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)

    application.include_router(health.router, prefix="/api")
    application.include_router(auth.router, prefix="/api")
    application.include_router(admin.router, prefix="/api")
    application.include_router(homework_help.router, prefix="/api")
    application.include_router(notifications.router, prefix="/api")
    application.include_router(household.router, prefix="/api")
    application.include_router(students.router, prefix="/api")
    application.include_router(curricula.router, prefix="/api")
    application.include_router(curriculum_plans.router, prefix="/api")
    application.include_router(catalog.router, prefix="/api")
    application.include_router(school_years.router, prefix="/api")
    application.include_router(settings_routes.router, prefix="/api")
    application.include_router(enrollments.router, prefix="/api")
    application.include_router(exceptions.router, prefix="/api")
    application.include_router(attendance.router, prefix="/api")
    application.include_router(books.router, prefix="/api")
    application.include_router(assignments.router, prefix="/api")
    application.include_router(evidence.router, prefix="/api")
    application.include_router(evidence.files_router, prefix="/api")
    application.include_router(dashboard.router, prefix="/api")
    application.include_router(calendar.router, prefix="/api")
    application.include_router(pacing.router, prefix="/api")
    application.include_router(recalibration.router, prefix="/api")
    application.include_router(portfolios.router, prefix="/api")
    application.include_router(reports.router, prefix="/api")

    index_path = Path(settings.index_html_path)
    static_dir = Path(settings.static_dir)
    sw_path = Path(__file__).resolve().parent.parent / "sw.js"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=static_dir), name="static")

    @application.get("/", include_in_schema=False)
    def app_shell() -> FileResponse:
        return FileResponse(index_path, headers={"Cache-Control": "no-cache"})

    @application.get("/sw.js", include_in_schema=False)
    def service_worker() -> Response:
        if not sw_path.is_file():
            return Response(status_code=404, media_type="text/javascript")
        return FileResponse(
            sw_path,
            media_type="text/javascript",
            headers={
                "Cache-Control": "no-cache",
                "Service-Worker-Allowed": "/",
            },
        )

    return application


app = create_app()
