import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ledger.repository import get_traces_events, get_window
from backend.ml.counterfactual.backtest import compare_runs
from backend.ml.counterfactual.interventions import Intervention


async def events_for_run(connection: Any, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    start = datetime.fromisoformat(manifest["injection_time"])
    end = datetime.fromisoformat(manifest["fault_off_time"])
    window = await get_window(connection, start, end, type="http.request", limit=250)
    roots = [event for event in window if event["parent_span_id"] is None]
    return await get_traces_events(connection, sorted({event["trace_id"] for event in roots}))


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a simulated intervention with a separately recorded real-fix run"
    )
    parser.add_argument("--bug-run", type=Path, required=True)
    parser.add_argument("--fixed-run", type=Path, required=True)
    parser.add_argument("--intervention", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/backtest.json"))
    args = parser.parse_args()
    pool = await create_pool(get_settings())
    try:
        async with pool.acquire() as connection:
            before = await events_for_run(connection, json.loads(args.bug_run.read_text()))
            after = await events_for_run(connection, json.loads(args.fixed_run.read_text()))
        intervention = TypeAdapter(Intervention).validate_json(args.intervention.read_text())
        result = compare_runs(before, after, intervention)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
        if not result["passed"]:
            raise SystemExit(1)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
