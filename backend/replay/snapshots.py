from datetime import datetime
from typing import Any

from backend.common.metrics import DIGEST_MISMATCH

from .state import SystemState

SNAPSHOT_LOCK = 17031704


async def invalidate_from(connection: Any, ended_at: datetime) -> None:
    await connection.execute("SELECT pg_advisory_xact_lock($1)", SNAPSHOT_LOCK)
    await connection.execute("DELETE FROM snapshots WHERE cut_ended_at >= $1", ended_at)


class Snapshots:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    async def latest_before(self, until: datetime) -> SystemState | None:
        row = await self.connection.fetchrow(
            "SELECT state,digest FROM snapshots WHERE cut_ended_at<=$1 "
            "ORDER BY cut_ended_at DESC,cut_stream_id DESC,cut_sequence DESC LIMIT 1",
            until,
        )
        if row is None:
            return None
        state = SystemState.from_dict(row["state"])
        if state.digest() != row["digest"]:
            DIGEST_MISMATCH.inc()
            raise ValueError("snapshot digest mismatch")
        return state

    async def save(self, state: SystemState) -> None:
        if state.last_key is None:
            return
        await self.connection.execute(
            "INSERT INTO "
            "snapshots(cut_ended_at,cut_stream_id,cut_sequence,event_count,state,digest)"
            " "
            "VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING",
            *state.last_key,
            state.event_count,
            state.to_dict(),
            state.digest(),
        )
