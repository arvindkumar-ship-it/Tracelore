from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from pydantic import AwareDatetime

from backend.api.contracts import GraphEdge, GraphNode, GraphView

router = APIRouter()


@router.get("/graph", response_model=GraphView)
async def graph(request: Request, at: AwareDatetime | None = None) -> GraphView:
    at = at or datetime.now(UTC)
    async with request.app.state.pool.acquire() as connection:
        edges = await connection.fetch(
            "SELECT * FROM dependency_edges WHERE first_seen<=$1 AND last_seen >= $2",
            at,
            at - timedelta(days=7),
        )
        incidents = await connection.fetch(
            "SELECT services FROM incidents WHERE start_time <= $1 "
            "AND (closed_at IS NULL OR closed_at >= $1)",
            at,
        )
        reports = await connection.fetch(
            "SELECT report FROM rca_reports WHERE created_at<=$1 ORDER BY created_at DESC LIMIT 20",
            at,
        )
    anomalous = {f"svc:{service}" for row in incidents for service in row["services"]}
    roots = {row["report"]["report"]["root_cause_node"] for row in reports}
    nodes = sorted(
        {edge["caller"] for edge in edges} | {edge["callee"] for edge in edges} | anomalous
    )
    return GraphView(
        nodes=[
            GraphNode(id=node, anomalous=node in anomalous, root_candidate=node in roots)
            for node in nodes
        ],
        edges=[
            GraphEdge(
                source=edge["caller"],
                target=edge["callee"],
                calls=edge["call_count"],
                propagation=edge["caller"] in anomalous and edge["callee"] in anomalous,
            )
            for edge in edges
        ],
    )
