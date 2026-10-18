from dataclasses import dataclass
from typing import Any

from tracelore.canonical import compute_event_hash
from tracelore.chain import GENESIS_HASH

from backend.common.metrics import CHAIN_FINDINGS

from .records import wire_event


@dataclass(frozen=True)
class Finding:
    stream_id: str
    kind: str
    from_sequence: int
    to_sequence: int


def _check_event(
    event: dict[str, Any],
    previous_sequence: int,
    previous_hash: str,
    anchored_hash: str | None = None,
) -> list[Finding]:
    stream, sequence = event["stream_id"], event["sequence"]
    findings = []
    if sequence != previous_sequence + 1 and anchored_hash is None:
        findings.append(Finding(stream, "gap", previous_sequence + 1, sequence - 1))
    expected = anchored_hash or (previous_hash if sequence == previous_sequence + 1 else None)
    if expected is not None and event["prev_event_hash"] != expected:
        findings.append(Finding(stream, "break", max(0, sequence - 1), sequence))
    if compute_event_hash(event) != event["event_hash"]:
        findings.append(Finding(stream, "break", sequence, sequence))
    return findings


def verify_events(events: list[dict[str, Any]], stream_id: str) -> list[Finding]:
    findings = []
    previous_hash, previous_sequence = GENESIS_HASH, 0
    for event in sorted(events, key=lambda event: event["sequence"]):
        if event["stream_id"] != stream_id:
            raise ValueError("mixed streams in chain verifier")
        findings.extend(_check_event(event, previous_sequence, previous_hash))
        previous_hash, previous_sequence = event["event_hash"], event["sequence"]
    return findings


async def verify_stream(connection: Any, stream_id: str) -> list[Finding]:
    previous_hash, previous_sequence = GENESIS_HASH, 0
    findings = []
    async with connection.transaction():
        async for row in connection.cursor(
            """
            SELECT e.*,p.event_hash AS anchored_prev_hash FROM events e
            LEFT JOIN stream_positions p ON p.stream_id=e.stream_id AND p.sequence=e.sequence-1
            WHERE e.stream_id=$1 ORDER BY e.sequence
        """,
            stream_id,
            prefetch=5000,
        ):
            event = wire_event(row)
            new = _check_event(event, previous_sequence, previous_hash, row["anchored_prev_hash"])
            for finding in new:
                await _save_finding(connection, finding)
            findings.extend(new)
            previous_hash, previous_sequence = event["event_hash"], event["sequence"]
    return findings


async def _save_finding(connection: Any, finding: Finding) -> None:
    identifier = await connection.fetchval(
        """
        INSERT INTO chain_findings(stream_id,kind,from_sequence,to_sequence)
        VALUES($1,$2,$3,$4) ON CONFLICT DO NOTHING RETURNING id
    """,
        finding.stream_id,
        finding.kind,
        finding.from_sequence,
        finding.to_sequence,
    )
    if identifier is not None:
        CHAIN_FINDINGS.labels(finding.kind).inc()
