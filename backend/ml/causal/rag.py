import asyncio
from functools import lru_cache
from typing import Any

from tracelore.canonical import canonical_json

from .evidence import sanitize_name


@lru_cache(maxsize=1)
def _model() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def signature_text(incident: Any) -> str:
    symptoms = sorted(
        {
            f"{signal.kind}:{signal.metric or signal.anomaly_kind}:{signal.direction}"
            for signal in incident.signals
        }
    )
    return canonical_json(
        {
            "services": sorted(sanitize_name(service) for service in incident.services),
            "symptoms": symptoms,
        }
    ).decode()


async def embed(signature: str) -> list[float]:
    def encode() -> list[float]:
        return list(map(float, _model().encode(signature, normalize_embeddings=True)))

    return await asyncio.to_thread(encode)


async def retrieve(
    connection: Any, signature: str, top_k: int = 3, min_similarity: float = 0.6
) -> list[dict[str, Any]]:
    if not await connection.fetchval(
        "SELECT EXISTS(SELECT 1 FROM past_incidents WHERE embedding IS NOT NULL)"
    ):
        return []
    embedding = str(await embed(signature))
    rows = await connection.fetch(
        "SELECT id,root_cause_node,root_cause,resolution,1-(embedding<=>$1::vector) AS similarity "
        "FROM past_incidents WHERE embedding IS NOT NULL AND 1-(embedding<=>$1::vector)>=$2 "
        "ORDER BY embedding<=>$1::vector LIMIT $3",
        embedding,
        min_similarity,
        top_k,
    )
    return [dict(row) | {"id": str(row["id"])} for row in rows]


async def index_resolved(
    connection: Any,
    incident: Any,
    node: str,
    cause: str,
    resolution: str,
    embeddings_enabled: bool = False,
) -> None:
    signature = signature_text(incident)
    embedding = str(await embed(signature)) if embeddings_enabled else None
    await connection.execute(
        "INSERT INTO "
        "past_incidents(id,signature_text,root_cause_node,root_cause,resolution,services,embedding)"
        " "
        "VALUES($1,$2,$3,$4,$5,$6,$7::vector) ON CONFLICT(id) DO UPDATE SET "
        "root_cause_node=EXCLUDED.root_cause_node,root_cause=EXCLUDED.root_cause,"
        "resolution=EXCLUDED.resolution,embedding=EXCLUDED.embedding",
        incident.id,
        signature,
        sanitize_name(node),
        cause[:1000],
        resolution[:1000],
        incident.services,
        embedding,
    )


async def index_pending(connection: Any) -> int:
    rows = await connection.fetch(
        "SELECT id,signature_text FROM past_incidents WHERE embedding IS NULL LIMIT 20"
    )
    for row in rows:
        vector = str(await embed(row["signature_text"]))
        await connection.execute(
            "UPDATE past_incidents SET embedding=$2::vector WHERE id=$1", row["id"], vector
        )
    return len(rows)
