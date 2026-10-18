import gzip
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import monotonic

import pytest
from tracelore import Tracelore, TraceloreConfig

pytestmark = pytest.mark.unit


def test_network_outage_spools_while_sender_waits_and_recovers(tmp_path):
    recovered = threading.Event()
    accepted = set()
    attempted = threading.Event()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(gzip.decompress(self.rfile.read(int(self.headers["Content-Length"]))))
            attempted.set()
            if not recovered.is_set():
                self.send_response(500)
                self.end_headers()
                return
            with lock:
                accepted.update(event["event_id"] for event in body["events"])
            payload = json.dumps(
                {"accepted": len(body["events"]), "duplicates": 0, "rejected": []}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = Tracelore(
        TraceloreConfig(
            api_key="test",
            service="delivery",
            endpoint=f"http://127.0.0.1:{server.server_port}/ingest",
            spool_dir=tmp_path,
            flush_interval_ms=20,
            batch_size=10,
        )
    )
    try:
        client.start()
        for _ in range(40):
            client.record(
                "http.request",
                {"method": "GET", "route": "/x", "status_code": 200},
                started_at=datetime.now(UTC),
                duration_ms=1,
            )
        assert attempted.wait(2)
        deadline = monotonic() + 2
        while client.spool.spooled < 40 and monotonic() < deadline:
            threading.Event().wait(0.02)
        assert client.spool.spooled == 40
        recovered.set()
        deadline = monotonic() + 5
        while len(accepted) < 40 and monotonic() < deadline:
            threading.Event().wait(0.02)
        assert len(accepted) == 40
    finally:
        client.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(2)
