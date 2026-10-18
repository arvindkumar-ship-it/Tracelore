from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingTrace:
    events: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_seen: float = 0
    root_seen: float | None = None


class TraceAssembler:
    def __init__(self, max_open: int = 50_000) -> None:
        self.pending: dict[str, PendingTrace] = {}
        self.max_open = max_open
        self.evictions = 0

    def add(self, event: dict[str, Any], received_at: float) -> None:
        trace_id = event["trace_id"]
        if trace_id not in self.pending and len(self.pending) >= self.max_open:
            oldest = min(self.pending, key=lambda key: self.pending[key].last_seen)
            del self.pending[oldest]
            self.evictions += 1
        trace = self.pending.setdefault(trace_id, PendingTrace())
        trace.events[event["event_id"]] = event
        trace.last_seen = received_at
        if event["parent_span_id"] is None:
            trace.root_seen = received_at

    def ready(self, at: float) -> list[tuple[str, list[dict[str, Any]]]]:
        complete = []
        for trace_id, trace in list(self.pending.items()):
            if at - trace.last_seen >= 30 or (
                trace.root_seen is not None and at - trace.root_seen >= 2
            ):
                events = sorted(
                    trace.events.values(),
                    key=lambda event: (event["timestamp"], event["ended_at"], event["event_id"]),
                )
                complete.append((trace_id, events))
                del self.pending[trace_id]
        return complete
