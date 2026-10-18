from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sqlalchemy import event

from ..client import Tracelore
from .sql import normalize_sql, parse_table_and_operation, query_attributes

__all__ = ["instrument", "normalize_sql", "parse_table_and_operation"]


def instrument(engine: Any, client: Tracelore) -> None:
    def before(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        context._tracelore_started = (datetime.now(UTC), perf_counter())

    def after(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        started_at, started = context._tracelore_started
        client.record(
            "db.query",
            query_attributes(statement, cursor.rowcount),
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )

    def failed(context: Any) -> None:
        if context.execution_context is None:
            return
        started_at, started = context.execution_context._tracelore_started
        client.record(
            "db.query",
            query_attributes(context.statement or ""),
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
            status="error",
        )

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    event.listen(engine, "handle_error", failed)
