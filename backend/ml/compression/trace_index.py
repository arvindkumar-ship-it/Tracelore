from pathlib import Path
from typing import Any
from uuid import UUID

import pyarrow as arrow
import pyarrow.parquet as parquet

INDEX_SCHEMA = arrow.schema([("trace_id", arrow.binary(16)), ("row_group", arrow.int32())])


def index_rows(events: list[dict[str, Any]], group: int) -> Any:
    return arrow.Table.from_pylist(
        [
            {"trace_id": UUID(trace_id).bytes, "row_group": group}
            for trace_id in sorted({event["trace_id"] for event in events})
        ],
        schema=INDEX_SCHEMA,
    )


def find_groups(index_path: Path, trace_id: str) -> list[int]:
    table = parquet.read_table(index_path, filters=[("trace_id", "=", UUID(trace_id).bytes)])
    return sorted(set(table.column("row_group").to_pylist()))
