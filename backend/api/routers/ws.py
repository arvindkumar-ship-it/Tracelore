import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect

from backend.api.auth import require_dashboard, verify_token
from backend.api.contracts import LiveFrame, ServiceMetric
from backend.common.errors import ApiError

router = APIRouter()


@router.websocket("/ws/live")
async def live(socket: WebSocket) -> None:
    settings = socket.app.state.settings
    if socket.headers.get("origin") != settings.dashboard_origin:
        await socket.close(code=1008)
        return
    await socket.accept()
    try:
        message = await asyncio.wait_for(socket.receive_json(), 5)
        verify_token(message.get("token", ""), settings, datetime.now(UTC))
        version = max(0, int(message.get("last_incident_version", 0)))
        while True:
            verify_token(message["token"], settings, datetime.now(UTC))
            frame = await _frame(socket, version)
            version = frame.incident_version
            await socket.send_text(frame.model_dump_json())
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        return
    except (ApiError, TimeoutError, ValueError, TypeError, KeyError):
        await socket.close(code=1008)


async def _frame(socket: WebSocket | Request, version: int) -> LiveFrame:
    async with socket.app.state.pool.acquire() as connection:
        rows = await connection.fetch(
            "SELECT service,count(*) AS count,count(*) FILTER(WHERE status='error') AS errors,"
            "percentile_cont(0.95) WITHIN GROUP(ORDER BY duration_ms) AS p95_ms FROM events "
            "WHERE type='http.request' AND ended_at>now()-interval '10 seconds' GROUP BY service"
        )
        if version == 0:
            version = int(
                await connection.fetchval("SELECT COALESCE(max(version),0) FROM incident_changes")
            )
        changes = await connection.fetch(
            "SELECT version,body FROM incident_changes WHERE version>$1 ORDER BY version LIMIT 500",
            version,
        )
        event_count = await connection.fetchval(
            "SELECT count(*) FROM events WHERE received_at>now()-interval '10 seconds'"
        )
    requests, errors = sum(row["count"] for row in rows), sum(row["errors"] for row in rows)
    return LiveFrame(
        events_per_sec=event_count / 10,
        error_rate=errors / max(requests, 1),
        per_service={
            row["service"]: ServiceMetric(
                count=row["count"], errors=row["errors"], p95_ms=row["p95_ms"]
            )
            for row in rows
        },
        incidents=[dict(row["body"]) for row in changes],
        incident_version=changes[-1]["version"] if changes else version,
        heartbeat=datetime.now(UTC),
    )


@router.get("/live", response_model=LiveFrame, dependencies=[Depends(require_dashboard)])
async def live_snapshot(request: Request, last_incident_version: int = Query(0, ge=0)) -> LiveFrame:
    return await _frame(request, last_incident_version)
