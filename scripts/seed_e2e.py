import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from tracelore.chain import HashChain
from tracelore.config import TraceloreConfig
from tracelore.event import build_event

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ingest.schemas import EventIn
from backend.ledger.repository import insert_events
from backend.ml.anomaly.contracts import Signal
from backend.ml.anomaly.incidents import save_signals
from backend.ml.causal.evidence import build_bundle
from backend.ml.causal.grounding import rules_report
from backend.ml.causal.propagation import Candidate
from backend.ml.causal.rca import RcaView


def fixture_events() -> tuple[str, list[dict]]:
    trace_id, root = str(uuid4()), str(uuid4())
    config = TraceloreConfig(api_key="fixture", service="e2e-gateway", instance_id=str(uuid4()))
    chain = HashChain(config.stream_id)
    start = datetime.now(UTC) - timedelta(seconds=60)
    events = []
    for index in range(9999):
        events.append(
            chain.seal(
                build_event(
                    config,
                    "db.query",
                    {
                        "operation": "select",
                        "db_table": "inventory",
                        "rows": 1,
                        "query_hash": "a" * 64,
                    },
                    trace_id,
                    str(uuid4()),
                    root,
                    start + timedelta(microseconds=index * 1000),
                    0.5,
                    "ok",
                )
            )
        )
    events.append(
        chain.seal(
            build_event(
                config,
                "http.request",
                {"method": "POST", "route": "/e2e", "status_code": 500},
                trace_id,
                root,
                None,
                start,
                11000,
                "error",
            )
        )
    )
    return trace_id, events


async def main() -> None:
    settings = get_settings()
    pool = await create_pool(settings, owner=True)
    trace_id, events = fixture_events()
    at = datetime.now(UTC)
    try:
        async with pool.acquire() as connection:
            for index in range(0, len(events), 1000):
                async with connection.transaction():
                    await insert_events(
                        connection,
                        [EventIn.model_validate(event) for event in events[index : index + 1000]],
                        at,
                        30,
                    )
            signal = Signal(
                id="e2e:" + str(uuid4()),
                kind="sequence",
                service="e2e-gateway",
                route="/e2e",
                detected_at=at,
                estimated_start=at - timedelta(seconds=60),
                confidence=0.95,
                event_id=events[-1]["event_id"],
                trace_id=trace_id,
            )
            incident = (await save_signals(connection, [signal]))[0]
            facts = [
                {
                    "kind": kind,
                    "node": "svc:e2e-gateway",
                    "text": "E2E fixture recorded span.",
                    "data": {
                        "event_id": events[-1]["event_id"],
                        "trace_id": trace_id,
                        "duration_ms": 11000,
                    },
                }
                for kind in ("event", "metric", "change_point")
            ]
            bundle = build_bundle([Candidate("svc:e2e-gateway", 0.8, {})], facts)
            report = RcaView(
                incident_id=incident.id, source="rules", report=rules_report(bundle), bundle=bundle
            )
            await connection.execute(
                "INSERT INTO rca_reports(incident_id,version,report,source) VALUES($1,1,$2,$3)",
                incident.id,
                report.model_dump(mode="json"),
                "rules",
            )
            path = Path("artifacts/e2e.json")
            path.parent.mkdir(exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "incident_id": str(incident.id),
                        "trace_id": trace_id,
                        "secret": settings.tracelore_secret.get_secret_value(),
                    }
                )
            )
            path.chmod(0o600)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
