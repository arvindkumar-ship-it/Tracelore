from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .contracts import Signal


class Incident(BaseModel):
    id: UUID
    status: str = "open"
    opened_at: datetime
    closed_at: datetime | None = None
    start_event_id: UUID | None = None
    start_time: datetime
    services: list[str]
    confidence: float
    signals: list[Signal] = Field(default_factory=list)
    updated_at: datetime
    version: int = 1
    signal_count: int = 0


def fuse(
    signals: list[Signal],
    open_incidents: list[Incident],
    neighbours: dict[str, set[str]] | None = None,
) -> list[Incident]:
    changed: dict[UUID, Incident] = {}
    for signal in sorted(signals, key=lambda signal: (signal.detected_at, signal.id)):
        if signal.confidence <= 0 or not signal.incident_grade:
            continue
        incident = _match(signal, open_incidents, neighbours or {})
        if incident is None:
            incident = Incident(
                id=uuid4(),
                opened_at=signal.detected_at,
                start_time=signal.estimated_start,
                services=[signal.service],
                confidence=0,
                updated_at=signal.detected_at,
            )
            open_incidents.append(incident)
        if any(existing.id == signal.id for existing in incident.signals):
            continue
        incident.signals.append(signal)
        incident.services = sorted(set(incident.services) | {signal.service})
        incident.start_time = min(incident.start_time, signal.estimated_start)
        incident.updated_at = max(incident.updated_at, signal.detected_at)
        incident.confidence = 1 - (1 - incident.confidence) * (1 - signal.confidence)
        incident.signal_count += 1
        incident.version += 1
        changed[incident.id] = incident
    return sorted(changed.values(), key=lambda incident: (incident.opened_at, str(incident.id)))


def _match(
    signal: Signal, incidents: list[Incident], neighbours: dict[str, set[str]]
) -> Incident | None:
    related = {signal.service} | neighbours.get(signal.service, set())
    return next(
        (
            incident
            for incident in incidents
            if set(incident.services) & related
            and abs(signal.detected_at - incident.updated_at) <= timedelta(seconds=120)
        ),
        None,
    )
