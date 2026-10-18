import pyarrow as arrow

SCHEMA_VERSION = 1
ATTRIBUTE_TYPES = {
    "method": arrow.string(),
    "route": arrow.string(),
    "status_code": arrow.int32(),
    "host": arrow.string(),
    "downstream_service": arrow.string(),
    "timeout_ms": arrow.int64(),
    "operation": arrow.string(),
    "db_table": arrow.string(),
    "query_hash": arrow.binary(32),
    "rows": arrow.int64(),
    "key_hash": arrow.binary(32),
    "hit": arrow.bool_(),
    "queue": arrow.string(),
    "message_hash": arrow.binary(32),
    "exception_type": arrow.string(),
}
SCHEMA = arrow.schema(
    [
        ("event_id", arrow.binary(16)),
        ("trace_id", arrow.binary(16)),
        ("span_id", arrow.binary(16)),
        ("parent_uuid", arrow.binary(16)),
        ("parent_ordinal", arrow.int32()),
        ("stream_id", arrow.string()),
        ("sequence_delta", arrow.int64()),
        ("ended_us", arrow.int64()),
        ("timestamp_delta_us", arrow.int64()),
        ("duration_ms", arrow.float64()),
        ("service", arrow.string()),
        ("type", arrow.string()),
        ("status", arrow.string()),
        ("payload_hash", arrow.binary(32)),
        ("prev_event_hash", arrow.binary(32)),
        *[(f"attr_{name}", kind) for name, kind in ATTRIBUTE_TYPES.items()],
    ],
    metadata={b"tracelore_schema_version": str(SCHEMA_VERSION).encode()},
)
DICTIONARY_COLUMNS = [
    "service",
    "type",
    "status",
    "stream_id",
    "attr_route",
    "attr_method",
    "attr_operation",
    "attr_db_table",
    "attr_downstream_service",
    "attr_host",
    "attr_queue",
]
