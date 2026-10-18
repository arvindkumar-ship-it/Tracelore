import asyncio
import json
from collections import Counter, defaultdict
from pathlib import Path

import torch

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ledger.records import wire_event
from backend.ml.anomaly.seq_model import train_sequences
from backend.ml.anomaly.tokens import END, START, UNKNOWN, tokenize
from backend.ml.onnx_export import export_opset17


async def main() -> None:
    settings = get_settings()
    pool = await create_pool(settings)
    directory = settings.model_dir / "sequence"
    try:
        async with pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT e.* FROM events e WHERE ended_at>now()-interval '7 days'
                AND NOT EXISTS(SELECT 1 FROM incidents i WHERE e.service=ANY(i.services)
                    AND e.ended_at BETWEEN i.start_time
                    AND COALESCE(i.closed_at,now())+interval '30 minutes')
                ORDER BY timestamp,ended_at LIMIT 200000
            """)
        grouped = defaultdict(list)
        for row in rows:
            grouped[str(row["trace_id"])].append(wire_event(row))
        traces = [
            [tokenize(event) for event in events]
            for events in grouped.values()
            if any(event["parent_span_id"] is None for event in events)
            and all(event["status"] == "ok" for event in events)
        ]
        await asyncio.to_thread(train_export, traces, directory)
    finally:
        await pool.close()


def train_export(traces: list[list[str]], directory: Path) -> None:
    if len(traces) < 100:
        raise ValueError("at least 100 clean, time-ordered traces are required")
    split = int(len(traces) * 0.8)
    counts = Counter(token for trace in traces[:split] for token in trace)
    frequent = [
        token
        for token, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if count >= 5
    ][:1997]
    vocabulary = {token: index for index, token in enumerate([START, END, UNKNOWN, *frequent])}
    ids = [
        [
            vocabulary[START],
            *[vocabulary.get(token, vocabulary[UNKNOWN]) for token in trace],
            vocabulary[END],
        ]
        for trace in traces
    ]
    model, calibration = train_sequences(ids[:split], ids[split:], len(vocabulary))
    directory.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), directory / "sequence.pt")
    export_opset17(
        model,
        (torch.zeros((1, 64), dtype=torch.long),),
        directory / "sequence.onnx",
        ["tokens"],
        ["logits"],
    )
    (directory / "sequence.json").write_text(json.dumps({"vocabulary": vocabulary, **calibration}))


if __name__ == "__main__":
    asyncio.run(main())
