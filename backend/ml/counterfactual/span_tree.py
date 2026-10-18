from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from backend.common.time import microseconds


@dataclass
class Span:
    event: dict[str, Any]
    start_us: int
    duration_us: int
    status: str
    original_start_us: int
    original_duration_us: int
    original_status: str
    children: list["Span"] = field(default_factory=list)
    removed: bool = False
    duration_override: bool = False
    new_timeout: bool = False

    @property
    def end_us(self) -> int:
        return self.start_us + self.duration_us


@dataclass
class TraceTree:
    trace_id: str
    spans: dict[str, Span]
    roots: list[Span]

    @property
    def root(self) -> Span:
        return next(
            (
                span
                for span in self.roots
                if span.event["type"] == "http.request" and span.event["parent_span_id"] is None
            ),
            self.roots[0],
        )


def build_trees(events: list[dict[str, Any]]) -> list[TraceTree]:
    traces: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        traces[event["trace_id"]].append(event)
    return [_build(trace_id, trace) for trace_id, trace in sorted(traces.items())]


def _build(trace_id: str, events: list[dict[str, Any]]) -> TraceTree:
    spans = {}
    for event in sorted(events, key=lambda event: (event["timestamp"], event["event_id"])):
        start, duration = microseconds(event["timestamp"]), round(event["duration_ms"] * 1000)
        if event["span_id"] in spans:
            raise ValueError("duplicate span identity in trace")
        spans[event["span_id"]] = Span(
            event, start, duration, event["status"], start, duration, event["status"]
        )
    roots = []
    for span in spans.values():
        parent = spans.get(span.event["parent_span_id"])
        if parent is None:
            roots.append(span)
        else:
            parent.children.append(span)
    _check_cycles(spans)
    if not roots:
        raise ValueError("span tree has no root")
    return TraceTree(trace_id, spans, roots)


def _check_cycles(spans: dict[str, Span]) -> None:
    complete: set[str] = set()
    for span_id in spans:
        path: set[str] = set()
        current: str | None = span_id
        while current in spans and current not in complete:
            if current in path:
                raise ValueError("cyclic span parents")
            path.add(current)
            current = spans[current].event["parent_span_id"]
        complete |= path
