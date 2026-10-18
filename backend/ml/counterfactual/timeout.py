from statistics import median

from .interventions import TimeoutChange
from .span_tree import Span, TraceTree


def _matches(span: Span, intervention: TimeoutChange) -> bool:
    return bool(
        span.event["type"] == "http.client"
        and span.event["service"] == intervention.caller
        and span.event["attributes"]["downstream_service"] == intervention.callee
    )


def apply_timeout(trees: list[TraceTree], intervention: TimeoutChange) -> set[str]:
    successes = [
        span
        for tree in trees
        for span in tree.spans.values()
        if _matches(span, intervention) and span.status == "ok"
    ]
    overheads = [
        max(0, span.duration_us - child.duration_us)
        for span in successes
        for child in span.children
        if child.event["type"] == "http.request"
    ]
    overhead = round(median(overheads)) if overheads else 0
    unknown = set()
    for tree in trees:
        for span in tree.spans.values():
            if _matches(span, intervention) and not _change(span, intervention, overhead):
                unknown.add(tree.trace_id)
    return unknown


def _change(span: Span, intervention: TimeoutChange, overhead: int) -> bool:
    timeout = intervention.new_timeout_ms * 1000
    if span.status == "ok":
        if span.duration_us > timeout:
            span.duration_us, span.status, span.new_timeout = timeout, "error", True
            span.duration_override = True
        return True
    old_timeout = span.event["attributes"]["timeout_ms"]
    if old_timeout is None or span.duration_us < 0.95 * old_timeout * 1000:
        return True
    server = next((child for child in span.children if child.event["type"] == "http.request"), None)
    if server is None:
        return False
    true_duration = server.duration_us + overhead
    span.duration_us = min(true_duration, timeout)
    span.status = server.status if true_duration <= timeout else "error"
    span.duration_override = True
    return True
