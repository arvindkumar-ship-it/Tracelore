import argparse
import asyncio

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "service",
        choices=("api", "ingest", "workers", "detector", "migrate", "demo", "bootstrap", "topics"),
    )
    args = parser.parse_args()
    if args.service in ("api", "ingest"):
        uvicorn.run(
            f"backend.{args.service}.main:app",
            host="0.0.0.0",  # noqa: S104 - container ingress is restricted by Compose/Caddy.
            port=8000 if args.service == "api" else 8001,
            proxy_headers=False,
        )
    elif args.service == "demo":
        uvicorn.run(
            "bench.demo_app.main:app",
            host="0.0.0.0",  # noqa: S104 - container ingress uses private Docker networking.
            port=8010,
            proxy_headers=False,
        )
    else:
        from importlib import import_module

        module = {
            "workers": "backend.workers.main",
            "detector": "backend.ml.anomaly.consumer",
            "migrate": "backend.ledger.migrate",
            "bootstrap": "scripts.bootstrap",
            "topics": "scripts.create_topics",
        }[args.service]
        asyncio.run(import_module(module).main())


if __name__ == "__main__":
    main()
