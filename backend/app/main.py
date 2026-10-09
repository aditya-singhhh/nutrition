from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.ai.providers import AIGateway
from app.db_migrate import ensure_columns
from app.api.v1 import admin, auth_users, meals_ai, scan_foods
from app.core.config import Settings, get_settings
from app.core.db import make_engine, make_session_factory
from app.models import Base
from app.seed import seed_all

logger = logging.getLogger("healthcompanion")


def create_app(settings: Settings | None = None, gateway: AIGateway | None = None) -> FastAPI:
    s = settings or get_settings()
    logging.basicConfig(level=s.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s.resolved_jwt_secret()  # fail fast in staging/prod if the secret is missing

    engine = make_engine(s.database_url)
    factory = make_session_factory(engine)
    if s.env in ("dev", "test") or s.auto_create_tables:
        Base.metadata.create_all(engine)  # real prod should use migrations (Alembic - next step)
        ensure_columns(engine)
        if s.seed_on_startup:
            with factory() as db:
                seed_all(db)

    app = FastAPI(title="AI Health Companion API", version="0.1.0",
                  description="Nutrition guidance, not medical advice.")
    app.state.session_factory = factory
    app.state.engine = engine
    app.state.gateway = gateway or AIGateway.from_settings(s)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["Cache-Control"] = "no-store"  # responses can contain health data
        response.headers["X-Content-Type-Options"] = "nosniff"
        # path + status only: never log bodies, query strings or tokens
        logger.info("%s %s -> %s (%.0f ms) rid=%s", request.method, request.url.path, response.status_code,
                    (time.perf_counter() - t0) * 1000, rid)
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    @app.get("/health", tags=["health"])
    def liveness():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def readiness():
        with factory() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready"}

    for r in (auth_users.router, scan_foods.router, meals_ai.router, admin.router):
        app.include_router(r, prefix="/api/v1")
    return app


def get_app() -> FastAPI:  # uvicorn --factory app.main:get_app
    return create_app()
