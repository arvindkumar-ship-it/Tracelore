from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import UUID4, AwareDatetime, BaseModel, ConfigDict, Field, field_serializer
from tracelore.event import format_timestamp

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
EventType = Literal[
    "http.request",
    "http.client",
    "db.query",
    "cache.get",
    "cache.set",
    "cache.delete",
    "queue.publish",
    "queue.consume",
    "error",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EventIn(StrictModel):
    event_id: UUID4
    trace_id: UUID
    span_id: UUID
    parent_span_id: UUID | None
    stream_id: str = Field(min_length=3, max_length=240)
    sequence: int = Field(ge=1, le=2**53 - 1)
    timestamp: AwareDatetime
    ended_at: AwareDatetime
    duration_ms: float = Field(ge=0)
    service: str = Field(min_length=1, max_length=100)
    type: EventType
    status: Literal["ok", "error"]
    attributes: dict[str, Any]
    payload_hash: Hash
    prev_event_hash: Hash
    event_hash: Hash

    @field_serializer("timestamp", "ended_at", when_used="json")
    def serialize_timestamp(self, value: datetime) -> str:
        return format_timestamp(value)


class SdkStats(StrictModel):
    dropped: int = Field(default=0, ge=0)
    spooled: int = Field(default=0, ge=0)


class BatchIn(StrictModel):
    batch_id: UUID
    events: list[EventIn] = Field(min_length=1, max_length=1000)
    sdk_stats: SdkStats | None = None


class Rejection(StrictModel):
    event_id: str
    code: str


class IngestResult(StrictModel):
    accepted: int
    duplicates: int
    rejected: list[Rejection]
