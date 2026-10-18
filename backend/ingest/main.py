from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI
from prometheus_client import make_asgi_app
from redis.asyncio import Redis

from backend.common.body_limit import BodyLimit
from backend.common.db import create_pool
from backend.common.errors import ApiError, Code, install_errors
from backend.common.logging import configure_logging
from backend.common.metrics import INGEST_SECONDS
from backend.common.settings import get_settings

from .auth import ApiKeyCache, require_api_key
from .schemas import BatchIn, IngestResult
from .service import ingest_batch


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    configure_logging()
    app.state.settings = get_settings()
    app.state.pool = await create_pool(app.state.settings)
    app.state.redis = Redis.from_url(app.state.settings.redis_url)
    app.state.key_cache = ApiKeyCache()
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await app.state.pool.close()


def create_app() -> FastAPI:
    application = FastAPI(title="Tracelore Ingest", version="0.1.0", lifespan=lifespan)
    install_errors(application)
    application.add_middleware(BodyLimit, max_bytes=5 * 1024 * 1024)
    application.mount("/metrics", make_asgi_app())

    @application.post("/ingest", response_model=IngestResult)
    async def ingest(batch: BatchIn, key: Annotated[str, Depends(require_api_key)]) -> IngestResult:
        if len(batch.events) > application.state.settings.ingest_max_batch:
            raise ApiError(Code.TOO_LARGE, "Batch exceeds configured event limit")
        with INGEST_SECONDS.time():
            return await ingest_batch(application.state, batch, key)

    @application.get("/healthz")
    async def health() -> dict[str, str]:
        async with application.state.pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
        await application.state.redis.ping()
        return {"status": "ok", "delivery": "durable-outbox"}

    return application


app = create_app()
