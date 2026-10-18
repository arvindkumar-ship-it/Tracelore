from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

TRACE_HEADER = "x-tracelore-trace"
_trace_id: ContextVar[str | None] = ContextVar("tracelore_trace", default=None)
_span_id: ContextVar[str | None] = ContextVar("tracelore_span", default=None)


def current_ids() -> tuple[str | None, str | None]:
    return _trace_id.get(), _span_id.get()


@contextmanager
def span_scope(trace_id: str, span_id: str) -> Iterator[None]:
    trace_token, span_token = _trace_id.set(trace_id), _span_id.set(span_id)
    try:
        yield
    finally:
        _span_id.reset(span_token)
        _trace_id.reset(trace_token)


def header_value(trace_id: str, span_id: str) -> str:
    return f"{trace_id}:{span_id}"


def parse_header(value: str) -> tuple[str, str] | None:
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        return str(UUID(parts[0])), str(UUID(parts[1]))
    except ValueError:
        return None
