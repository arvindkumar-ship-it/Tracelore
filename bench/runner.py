import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from backend.common.db import create_pool
from backend.common.settings import get_settings
from backend.ledger.repository import get_window

from .faults.catalogue import Fault, load_catalogue
from .faults.injector import set_fault
from .report import write_report
from .scorer import score_scenario
from .traffic.load_generator import run_traffic

logger = logging.getLogger(__name__)


async def scenario(fault: Fault, seed: int, args: Any, settings: Any, pool: Any) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30, trust_env=False) as http:
        await set_fault(http, settings, None)
        await run_traffic(settings.demo_gateway_url, args.warm_seconds, seed, rate=args.rate)
        injection = datetime.now(UTC)
        await set_fault(http, settings, fault, seed=seed, enabled=not args.fixed)
        try:
            traffic = await run_traffic(
                settings.demo_gateway_url,
                args.fault_seconds,
                seed + 1,
                rate=args.rate,
                profile=fault.injection["flag"] if fault.rag_split == "control" else "normal",
            )
        finally:
            fault_off = datetime.now(UTC)
            await set_fault(http, settings, None)
        await run_traffic(
            settings.demo_gateway_url, args.recovery_seconds, seed + 2, rate=args.rate
        )
    end = datetime.now(UTC)
    async with pool.acquire() as connection:
        events = await get_window(
            connection, injection - timedelta(minutes=1), end, limit=5_000_000
        )
        incidents = [
            dict(row)
            for row in await connection.fetch(
                "SELECT * FROM incidents WHERE opened_at BETWEEN $1 AND $2", injection, end
            )
        ]
        reports = [
            dict(row)
            for row in await connection.fetch(
                (
                    "SELECT r.* FROM rca_reports r JOIN incidents i ON i.id=r.incident_id WHERE "
                    "i.opened_at BETWEEN $1 AND $2 ORDER BY r.version DESC"
                ),
                injection,
                end,
            )
        ]
    result = score_scenario(fault, injection, events, incidents, reports)
    result["seed"] = seed
    manifest = {
        "fault": fault.model_dump(),
        "seed": seed,
        "injection_time": injection.isoformat(),
        "fault_off_time": fault_off.isoformat(),
        "real_fix_applied": args.fixed,
        "ended_at": end.isoformat(),
        "traffic": asdict(traffic),
        "trace_ids": sorted({event["trace_id"] for event in events}),
        "score": result,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / f"{fault.id}-{seed}-{'fixed' if args.fixed else 'bug'}.json").write_text(
        json.dumps(manifest, default=str, indent=2)
    )
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run live, labelled faults; does not manufacture acceptance results"
    )
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--bug")
    parser.add_argument("--with-controls", action="store_true")
    parser.add_argument("--fixed", action="store_true")
    parser.add_argument("--seeds", type=int, nargs="+", default=[19, 23, 41])
    parser.add_argument("--warm-seconds", type=float, default=900)
    parser.add_argument("--fault-seconds", type=float, default=900)
    parser.add_argument("--recovery-seconds", type=float, default=660)
    parser.add_argument("--rate", type=float, default=20)
    parser.add_argument("--output", type=Path, default=Path("bench/reports"))
    args = parser.parse_args()
    if not args.all and not args.bug:
        parser.error("choose --all or --bug A01")
    faults = [
        fault
        for fault in load_catalogue()
        if (args.all or fault.id == args.bug)
        and (args.with_controls or fault.rag_split != "control")
    ]
    settings = get_settings()
    pool = await create_pool(settings)
    results = []
    try:
        for fault in faults:
            for seed in args.seeds:
                logger.info("scenario_start bug=%s seed=%s", fault.id, seed)
                results.append(await scenario(fault, seed, args, settings, pool))
        write_report(args.output, results)
    finally:
        await pool.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
