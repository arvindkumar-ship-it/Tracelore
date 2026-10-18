from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from backend.api.contracts import IncidentPage
from backend.common.cursors import decode_cursor, encode_cursor
from backend.common.errors import ApiError, Code
from backend.ml.anomaly.contracts import Signal
from backend.ml.anomaly.fusion import Incident
from backend.ml.anomaly.incidents import record_change
from backend.ml.causal.rag import index_resolved
from backend.ml.causal.rca import RcaView

router = APIRouter()
LIST_SQL = """
SELECT id,status,opened_at,closed_at,start_event_id,start_time,services,confidence,
updated_at,version,signal_count FROM incidents
WHERE ($1::text IS NULL OR status=$1)
AND ($2::timestamptz IS NULL OR (opened_at,id)<($2,$3))
ORDER BY opened_at DESC,id DESC LIMIT $4
"""


class Resolution(BaseModel):
    root_cause_node: str = Field(min_length=1, max_length=200)
    root_cause: str = Field(min_length=1, max_length=1000)
    resolution: str = Field(min_length=1, max_length=1000)


class SignalPage(BaseModel):
    items: list[Signal]
    next_cursor: str | None


@router.get("/incidents", response_model=IncidentPage)
async def list_incidents(
    request: Request,
    status: str | None = Query(None, pattern="^(open|resolved)$"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> IncidentPage:
    at, identifier = decode_cursor(cursor)
    try:
        last_id = UUID(identifier) if identifier else None
    except ValueError as error:
        raise ApiError(Code.BAD_REQUEST, "Invalid incident cursor") from error
    async with request.app.state.pool.acquire() as connection:
        rows = await connection.fetch(LIST_SQL, status, at, last_id, limit + 1)
    items = [Incident.model_validate(dict(row)) for row in rows[:limit]]
    cursor = encode_cursor(items[-1].opened_at, str(items[-1].id)) if len(rows) > limit else None
    return IncidentPage(items=items, next_cursor=cursor)


@router.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: UUID, request: Request) -> Incident:
    async with request.app.state.pool.acquire() as connection:
        row = await connection.fetchrow("SELECT * FROM incidents WHERE id=$1", incident_id)
    if row is None:
        raise ApiError(Code.NOT_FOUND, "Incident not found", 404)
    return Incident.model_validate(dict(row))


@router.get("/incidents/{incident_id}/rca", response_model=RcaView | None)
async def get_rca(incident_id: UUID, request: Request) -> RcaView | None:
    async with request.app.state.pool.acquire() as connection:
        value = await connection.fetchval(
            "SELECT report FROM rca_reports WHERE incident_id=$1 ORDER BY version DESC LIMIT 1",
            incident_id,
        )
        if value is None and not await connection.fetchval(
            "SELECT 1 FROM incidents WHERE id=$1", incident_id
        ):
            raise ApiError(Code.NOT_FOUND, "Incident not found", 404)
    return RcaView.model_validate(value) if value else None


@router.post("/incidents/{incident_id}/resolve", response_model=Incident)
async def resolve(incident_id: UUID, body: Resolution, request: Request) -> Incident:
    async with request.app.state.pool.acquire() as connection, connection.transaction():
        row = await connection.fetchrow(
            "UPDATE incidents SET status='resolved',closed_at=COALESCE(closed_at,now()), "
            "updated_at=now(),version=version+1 WHERE id=$1 RETURNING *",
            incident_id,
        )
        if row is None:
            raise ApiError(Code.NOT_FOUND, "Incident not found", 404)
        incident = Incident.model_validate(dict(row))
        await index_resolved(
            connection, incident, body.root_cause_node, body.root_cause, body.resolution
        )
        await record_change(connection, incident)
    return incident


@router.get("/incidents/{incident_id}/signals", response_model=SignalPage)
async def signal_history(
    incident_id: UUID,
    request: Request,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> SignalPage:
    at, identifier = decode_cursor(cursor)
    async with request.app.state.pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT * FROM incident_signals WHERE incident_id=$1 "
            "AND ($2::timestamptz IS NULL OR (detected_at,signal_id)>($2,$3)) "
            "ORDER BY detected_at,signal_id LIMIT $4",
            incident_id,
            at,
            identifier,
            limit + 1,
        )
    cursor = (
        encode_cursor(rows[limit - 1]["detected_at"], rows[limit - 1]["signal_id"])
        if len(rows) > limit
        else None
    )
    return SignalPage(
        items=[Signal.model_validate(row["body"]) for row in rows[:limit]], next_cursor=cursor
    )
