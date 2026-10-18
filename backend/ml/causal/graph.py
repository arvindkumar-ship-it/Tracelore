from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DependencyGraph:
    adjacency: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_edge(self, caller: str, callee: str) -> None:
        self.adjacency.setdefault(caller, set()).add(callee)
        self.adjacency.setdefault(callee, set())

    def dependencies(self, node: str) -> set[str]:
        return self.adjacency.get(node, set()).copy()

    def dependents(self, node: str) -> set[str]:
        return {caller for caller, dependencies in self.adjacency.items() if node in dependencies}

    def descendants(self, node: str) -> set[str]:
        return self._walk(node, reverse=False)

    def affected_dependents(self, node: str) -> set[str]:
        return self._walk(node, reverse=True)

    def _walk(self, node: str, reverse: bool) -> set[str]:
        visited, pending = {node}, [node]
        while pending:
            current = pending.pop()
            adjacent = self.dependents(current) if reverse else self.dependencies(current)
            for neighbour in sorted(adjacent - visited):
                visited.add(neighbour)
                pending.append(neighbour)
        return visited - {node}


def event_node(event: dict[str, Any]) -> str:
    kind, attributes = event["type"], event["attributes"]
    if kind == "db.query":
        return f"db:{attributes['db_table'] or '*'}"
    if kind.startswith("cache."):
        return f"cache:{event['service']}"
    if kind.startswith("queue."):
        return f"queue:{attributes['queue']}"
    if kind == "http.client":
        return f"svc:{attributes['downstream_service']}"
    return f"svc:{event['service']}"


async def load_graph(connection: Any) -> DependencyGraph:
    rows = await connection.fetch(
        "SELECT caller,callee FROM dependency_edges WHERE last_seen>now()-interval '7 days'"
    )
    graph = DependencyGraph()
    for row in rows:
        graph.add_edge(row["caller"], row["callee"])
    return graph


async def refresh_edges(connection: Any) -> None:
    await connection.execute("""
        INSERT INTO dependency_edges(caller,callee,kind,first_seen,last_seen,call_count)
        SELECT 'svc:'||service,CASE
            WHEN type='http.client' THEN 'svc:'||(attributes->>'downstream_service')
            WHEN type='db.query' THEN 'db:'||COALESCE(attributes->>'db_table','*')
            WHEN type LIKE 'cache.%' THEN 'cache:'||service
            ELSE 'queue:'||(attributes->>'queue') END,
            type,min(ended_at),max(ended_at),count(*)
        FROM events WHERE ended_at>now()-interval '7 days'
        AND (type IN ('http.client','db.query','queue.publish') OR type LIKE 'cache.%')
        GROUP BY 1,2,3 ON CONFLICT(caller,callee,kind) DO UPDATE SET
        first_seen=LEAST(dependency_edges.first_seen,EXCLUDED.first_seen),
        last_seen=EXCLUDED.last_seen,call_count=EXCLUDED.call_count
    """)
