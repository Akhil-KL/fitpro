import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, auth, chat, foods, tracking, users, workouts
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.db.base import Base
from app.db.session import get_engine, session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")


def init_db() -> None:
    import app.models  # noqa: F401  (register models)
    from app.services.nutrition_service import NutritionService

    settings = get_settings()
    if settings.auto_create_tables:
        Base.metadata.create_all(get_engine())
    db = session_factory()()
    try:
        added = NutritionService(db).seed_foods()
        db.commit()
        if added:
            log.info("Seeded %s foods", added)
    except Exception as exc:  # tables may not exist yet before `alembic upgrade head`
        db.rollback()
        log.warning("Food seeding skipped: %s", type(exc).__name__)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan,
                  docs_url="/docs" if settings.environment != "production" else None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        log.info("%s %s %s %.0fms rid=%s", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - start) * 1000, rid)
        return response

    api = APIRouter(prefix="/api/v1")
    for r in (auth, users, chat, foods, workouts, tracking, analytics):
        api.include_router(r.router)
    app.include_router(api)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "ai": settings.ai_provider if settings.ai_enabled else "rules", "auth": settings.auth_mode}

    return app


app = create_app()
