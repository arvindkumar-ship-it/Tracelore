from prometheus_client import Counter, Gauge, Histogram

INGEST_EVENTS = Counter("tracelore_ingest_events_total", "Ingestion outcomes", ["result"])
INGEST_SECONDS = Histogram("tracelore_ingest_batch_seconds", "Durable batch ingestion")
LEDGER_SECONDS = Histogram("tracelore_ledger_insert_seconds", "Ledger COPY and insert")
PUBLISH_FAILURES = Counter("tracelore_kafka_publish_failures_total", "Kafka publish failures")
REPLAY_SECONDS = Histogram("tracelore_replay_seconds", "Deterministic fold duration")
DIGEST_MISMATCH = Counter("tracelore_replay_digest_mismatch_total", "Replay self-check failures")
DETECTOR_LAG = Gauge("tracelore_detector_lag_seconds", "Most recent live-event consumer lag")
BOCPD_ALARMS = Counter("tracelore_bocpd_alarms_total", "Change-point alarms")
OPEN_INCIDENTS = Gauge("tracelore_open_incidents", "Unresolved incidents")
RCA_SECONDS = Histogram("tracelore_rca_seconds", "RCA execution time")
GROUNDING_FAILURES = Counter(
    "tracelore_rca_grounding_failures_total", "Rejected ungrounded reports"
)
COMPRESSION_RATIO = Gauge("tracelore_compression_ratio", "Archive bytes divided by source bytes")
CHAIN_FINDINGS = Counter("tracelore_chain_findings_total", "Chain verifier findings", ["kind"])
SDK_DROPPED = Counter("tracelore_sdk_dropped_events_total", "SDK spool capacity losses")
JOB_SECONDS = Histogram("tracelore_job_seconds", "Worker job execution", ["job"])
JOB_FAILURES = Counter("tracelore_job_failures_total", "Worker failures", ["job"])
TRACE_EVICTIONS = Counter("tracelore_trace_evictions_total", "Open trace memory evictions")
for result in ("accepted", "duplicate", "rejected"):
    INGEST_EVENTS.labels(result)
for kind in ("gap", "break"):
    CHAIN_FINDINGS.labels(kind)
