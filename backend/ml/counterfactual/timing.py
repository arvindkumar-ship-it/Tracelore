import heapq

from .span_tree import Span


def union_length(intervals: list[tuple[int, int]]) -> int:
    total, previous_end = 0, None
    for start, end in sorted(intervals):
        if end < start:
            raise ValueError("invalid interval")
        total += max(0, end - max(start, previous_end if previous_end is not None else start))
        previous_end = max(end, previous_end if previous_end is not None else end)
    return total


def shift_subtree(span: Span, delta: int) -> None:
    pending = [span]
    while pending:
        current = pending.pop()
        current.start_us += delta
        pending.extend(current.children)


def recompute(span: Span) -> None:
    stack = [(span, False)]
    while stack:
        current, visited = stack.pop()
        if visited:
            _recompute_span(current)
        else:
            stack.append((current, True))
            stack.extend((child, False) for child in reversed(current.children))


def _shift_siblings(children: list[Span]) -> None:
    finished: list[tuple[int, int, int]] = []
    cumulative = 0
    for index, child in enumerate(children):
        while finished and finished[0][0] <= child.original_start_us:
            _, delta, _ = heapq.heappop(finished)
            cumulative += delta
        if cumulative:
            shift_subtree(child, cumulative)
        delta = (0 if child.removed else child.duration_us) - child.original_duration_us
        heapq.heappush(
            finished, (child.original_start_us + child.original_duration_us, delta, index)
        )


def _recompute_span(span: Span) -> None:
    children = sorted(
        span.children, key=lambda child: (child.original_start_us, child.event["span_id"])
    )
    original_union = union_length(
        [
            (child.original_start_us, child.original_start_us + child.original_duration_us)
            for child in children
            if child.event["type"] != "error"
        ]
    )
    _shift_siblings(children)
    active = [child for child in children if not child.removed and child.event["type"] != "error"]
    timeout = span.event["attributes"].get("timeout_ms")
    preserve_deadline = (
        span.event["type"] == "http.client"
        and span.original_status == "error"
        and timeout is not None
        and span.original_duration_us >= 0.95 * timeout * 1000
    )
    if not span.duration_override and not preserve_deadline:
        span.duration_us = max(
            0,
            span.original_duration_us
            - original_union
            + union_length([(child.start_us, child.end_us) for child in active]),
        )
    originally_failed = [
        child
        for child in children
        if child.original_status == "error" and child.event["type"] != "error"
    ]
    if any(child.status == "error" for child in active):
        span.status = "error"
    elif originally_failed and span.original_status == "error" and not preserve_deadline:
        span.status = "ok"
