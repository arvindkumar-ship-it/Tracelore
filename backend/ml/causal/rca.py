import asyncio
from dataclasses import asdict
from datetime import timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from backend.common.errors import ApiError, Code
from backend.common.metrics import RCA_SECONDS
from backend.common.settings import Settings
from backend.ml.anomaly.fusion import Incident

from .analysis import collect_facts
from .evidence import EvidenceBundle, EvidenceItem, build_bundle, sanitize_name
from .granger import test_edge
from .graph import load_graph
from .grounding import RootCauseReport
from .llm import explain
from .propagation import rank_candidates
from .rag import retrieve, signature_text
from .store import incident_events


class RcaView(BaseModel):
    incident_id: UUID
    source: str
    report: RootCauseReport
    bundle: EvidenceBundle


async def analyze_incident(connection: Any, incident_id: UUID, settings: Settings) -> RcaView:
    row = await connection.fetchrow("SELECT * FROM incidents WHERE id=$1", incident_id)
    if row is None:
        raise ApiError(Code.NOT_FOUND, "Incident not found", 404)
    incident = Incident.model_validate(dict(row))
    with RCA_SECONDS.time():
        return await _analyze(connection, incident, settings)


async def _analyze(connection: Any, incident: Incident, settings: Settings) -> RcaView:
    start, end = (
        incident.start_time - timedelta(minutes=60),
        incident.updated_at + timedelta(minutes=15),
    )
    graph = await load_graph(connection)
    events = await incident_events(connection, incident.start_time, end)
    rows = await connection.fetch(
        "SELECT * FROM node_buckets WHERE bucket_start BETWEEN $1 AND $2 ORDER BY bucket_start",
        start,
        end,
    )
    onsets, magnitudes, facts = await asyncio.to_thread(
        collect_facts, events, rows, incident.start_time
    )
    granger_scores = await _granger_support(graph, rows, onsets, facts)
    candidates = rank_candidates(graph, onsets, magnitudes, granger_scores, settings.rca_weights)
    bundle = build_bundle(candidates, facts)
    if settings.rag_enabled:
        bundle.similar_incidents = await retrieve(connection, signature_text(incident))
        for similar in bundle.similar_incidents:
            bundle.evidence.append(
                EvidenceItem(
                    id=f"E{len(bundle.evidence) + 1}",
                    kind="similar_incident",
                    node=sanitize_name(similar["root_cause_node"]),
                    text="A previously resolved incident has a similar deterministic signature.",
                    data={"incident_id": similar["id"], "similarity": similar["similarity"]},
                )
            )
    report, source = await explain(bundle, settings)
    view = RcaView(incident_id=incident.id, source=source, report=report, bundle=bundle)
    await connection.execute(
        "INSERT INTO rca_reports(incident_id,version,report,source) "
        "SELECT $1,COALESCE(max(version),0)+1,$2,$3 FROM rca_reports WHERE incident_id=$1",
        incident.id,
        view.model_dump(mode="json"),
        source,
    )
    return view


async def _granger_support(
    graph: Any, rows: list[Any], onsets: Any, facts: list[Any]
) -> dict[str, float]:
    import pandas as pd

    series: dict[str, dict[Any, float]] = {}
    for row in rows:
        series.setdefault(row["node_id"], {})[row["bucket_start"]] = row["p95_ms"]
    support: dict[str, float] = {}
    for caller in sorted(graph.adjacency):
        for callee in sorted(graph.dependencies(caller)):
            if caller not in onsets or callee not in onsets:
                continue
            result = await asyncio.to_thread(
                test_edge,
                pd.Series(series.get(callee, {})),
                pd.Series(series.get(caller, {})),
                5,
                callee,
                caller,
            )
            support[callee] = max(support.get(callee, 0), float(result.status == "supported"))
            facts.append(
                {
                    "kind": "granger",
                    "node": callee,
                    "text": "Directional time-series support; not a causal proof.",
                    "data": asdict(result),
                }
            )
    return support
