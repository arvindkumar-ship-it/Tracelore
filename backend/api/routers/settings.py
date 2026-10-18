import secrets
from typing import Annotated

from fastapi import APIRouter, Path, Request
from pydantic import BaseModel, Field
from tracelore.canonical import hash_payload

from backend.api.contracts import KeyCreated, KeyView, SettingsView
from backend.common.errors import ApiError, Code

router = APIRouter()


class KeyInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SamplingInput(BaseModel):
    enabled: bool


@router.get("/settings", response_model=SettingsView)
async def settings(request: Request) -> SettingsView:
    config = request.app.state.settings
    async with request.app.state.pool.acquire() as connection:
        services = await connection.fetch("SELECT DISTINCT service FROM events ORDER BY service")
        sampling = await connection.fetchval(
            "SELECT value FROM runtime_settings WHERE key='lossy_sampling_enabled'"
        )
    return SettingsView(
        tiering_enabled=config.enable_tiering,
        hot_retention_days=config.hot_retention_days,
        warm_retention_days=config.warm_retention_days,
        lossy_sampling_enabled=sampling if sampling is not None else config.lossy_sampling_enabled,
        llm_enabled=config.llm_enabled,
        rag_enabled=config.rag_enabled,
        services=[row["service"] for row in services],
    )


@router.get("/settings/keys", response_model=list[KeyView])
async def keys(request: Request) -> list[KeyView]:
    async with request.app.state.pool.acquire() as connection:
        rows = await connection.fetch("SELECT * FROM api_keys ORDER BY created_at DESC")
    return [KeyView.model_validate(dict(row)) for row in rows]


@router.post("/settings/keys", response_model=KeyCreated)
async def create_key(body: KeyInput, request: Request) -> KeyCreated:
    key = "orr_" + secrets.token_urlsafe(32)
    async with request.app.state.pool.acquire() as connection:
        await connection.execute(
            "INSERT INTO api_keys(key_hash,name) VALUES($1,$2)", hash_payload(key), body.name
        )
    return KeyCreated(key=key, name=body.name)


@router.delete("/settings/keys/{key_hash}", response_model=KeyView)
async def revoke_key(
    key_hash: Annotated[str, Path(pattern="^[0-9a-f]{64}$")], request: Request
) -> KeyView:
    async with request.app.state.pool.acquire() as connection:
        row = await connection.fetchrow(
            "UPDATE api_keys SET revoked_at=now() WHERE key_hash=$1 RETURNING *", key_hash
        )
    if row is None:
        raise ApiError(Code.NOT_FOUND, "API key not found", 404)
    return KeyView.model_validate(dict(row))


@router.put("/settings/sampling", response_model=SamplingInput)
async def sampling(body: SamplingInput, request: Request) -> SamplingInput:
    async with request.app.state.pool.acquire() as connection:
        await connection.execute(
            "INSERT INTO runtime_settings(key,value) VALUES('lossy_sampling_enabled',$1) "
            "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
            body.enabled,
        )
    return body
