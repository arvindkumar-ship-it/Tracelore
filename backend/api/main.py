import hmac
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from redis.asyncio import Redis

from backend.common.body_limit import BodyLimit
from backend.common.db import create_pool
from backend.common.errors import ApiError, Code, install_errors
from backend.common.logging import configure_logging
from backend.common.settings import get_settings
from backend.ml.baseline.serve import router as baseline_router
from backend.ml.compression.object_store import ObjectStore
from backend.ml.counterfactual.api import router as simulation_router
from backend.replay.api import router as replay_router

from .auth import LoginInput, TokenView, issue_token, require_dashboard
from .contracts import HealthView
from .routers import graph, incidents, settings, ws


@asynccontextmanager
async def lifespan(application: FastAPI) -> Any:
    configure_logging()
    application.state.settings = get_settings()
    application.state.pool = await create_pool(application.state.settings)
    application.state.redis = Redis.from_url(application.state.settings.redis_url)
    application.state.object_store = ObjectStore(application.state.settings)
    try:
        yield
    finally:
        await application.state.redis.aclose()
        await application.state.pool.close()


def create_app() -> FastAPI:
    application = FastAPI(title="Tracelore Control Plane", version="0.1.0", lifespan=lifespan)
    install_errors(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[get_settings().dashboard_origin],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.add_middleware(BodyLimit, max_bytes=5 * 1024 * 1024)
    application.mount("/metrics", make_asgi_app())
    for router in (
        incidents.router,
        graph.router,
        settings.router,
        replay_router,
        simulation_router,
        baseline_router,
    ):
        application.include_router(router, dependencies=[Depends(require_dashboard)])
    application.include_router(ws.router)
    application.post("/auth/token", response_model=TokenView)(login)
    application.get("/healthz", response_model=HealthView)(health)
    return application


async def login(body: LoginInput, request: Request) -> TokenView:
    peer = request.client.host if request.client else "unknown"
    from backend.ingest.ratelimit import check_rate

    await check_rate(request.app.state.redis, "login:" + peer, 1, 10)
    if not hmac.compare_digest(
        body.secret.get_secret_value(),
        request.app.state.settings.tracelore_secret.get_secret_value(),
    ):
        raise ApiError(Code.UNAUTHORIZED, "Invalid dashboard secret", 401)
    return issue_token(request.app.state.settings, datetime.now(UTC))


async def health(request: Request) -> HealthView:
    async with request.app.state.pool.acquire() as connection:
        await connection.fetchval("SELECT 1")
    await request.app.state.redis.ping()
    return HealthView(status="ok")


app = create_app()
