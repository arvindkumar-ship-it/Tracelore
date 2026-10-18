from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.ml.anomaly.fusion import Incident


class HealthView(BaseModel):
    status: str


class IncidentPage(BaseModel):
    items: list[Incident]
    next_cursor: str | None


class StateView(BaseModel):
    scope: Literal["observed"] = "observed"
    digest: str
    state: dict[str, Any]


class SpanColumns(BaseModel):
    id: list[str]
    event_id: list[str]
    parent: list[str | None]
    start_us: list[int]
    dur_us: list[int]
    service_idx: list[int]
    type_idx: list[int]
    status: list[str]


class SpanDictionary(BaseModel):
    services: list[str]
    types: list[str]


class TraceView(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    scope: Literal["observed"] = "observed"
    trace_id: UUID
    dictionary: SpanDictionary = Field(alias="dict")
    spans: SpanColumns
    digest: str


class GraphNode(BaseModel):
    id: str
    anomalous: bool
    root_candidate: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    calls: int
    propagation: bool


class GraphView(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class KeyView(BaseModel):
    key_hash: str
    name: str
    created_at: datetime
    revoked_at: datetime | None


class KeyCreated(BaseModel):
    key: str
    name: str


class SettingsView(BaseModel):
    hot_retention_days: int
    warm_retention_days: int
    tiering_enabled: bool
    lossy_sampling_enabled: bool
    llm_enabled: bool
    rag_enabled: bool
    services: list[str]


class ServiceMetric(BaseModel):
    count: int
    errors: int
    p95_ms: float


class LiveFrame(BaseModel):
    events_per_sec: float
    error_rate: float
    per_service: dict[str, ServiceMetric]
    incidents: list[dict[str, Any]] = Field(default_factory=list)
    incident_version: int
    heartbeat: datetime
