import atexit
import logging
import signal
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from .buffer import EventBuffer
from .canonical import hash_payload
from .chain import HashChain
from .config import TraceloreConfig
from .context import current_ids, span_scope
from .event import build_event
from .spool import Spool
from .transport import SendResult, Transport

logger = logging.getLogger(__name__)
RETRY_DELAYS = (0.2, 0.8)


class Tracelore:
    def __init__(self, config: TraceloreConfig) -> None:
        self.config = config
        self.chain = HashChain(config.stream_id)
        self.buffer = EventBuffer(config.max_buffer)
        self.spool = Spool(config.spool_dir / config.service, config.spool_max_mb)
        self.transport = Transport(config)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sender: threading.Thread | None = None
        self._lifecycle = threading.Lock()
        self._closed = False
        self.errors = 0

    def start(self) -> None:
        with self._lifecycle:
            if self._thread is not None or not self.config.enabled:
                return
            if self._closed:
                raise RuntimeError("create a new Tracelore client after shutdown")
            self._thread = threading.Thread(target=self._run_loop, name="tracelore", daemon=True)
            self._sender = threading.Thread(
                target=self._send_loop, name="tracelore-send", daemon=True
            )
            self._thread.start()
            self._sender.start()
            atexit.register(self.shutdown)
            if threading.current_thread() is threading.main_thread():
                if signal.getsignal(signal.SIGTERM) == signal.SIG_DFL:
                    signal.signal(signal.SIGTERM, self._terminate)

    def _terminate(self, signum: int, frame: Any) -> None:
        self.shutdown()
        raise SystemExit(128 + signum)

    def record(
        self,
        type: str,
        attributes: dict[str, Any],
        *,
        started_at: datetime,
        duration_ms: float,
        status: str = "ok",
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        payload: bytes | str | None = None,
    ) -> None:
        if not self.config.enabled:
            return
        try:
            current_trace, current_span = current_ids()
            event = build_event(
                self.config,
                type,
                attributes,
                trace_id or current_trace or str(uuid4()),
                span_id or str(uuid4()),
                parent_span_id if span_id is not None else parent_span_id or current_span,
                started_at,
                duration_ms,
                status,
                payload,
            )
            sealed = self.chain.seal(event)
            if self._closed or not self.buffer.put(sealed):
                self.spool.append([sealed])
        except Exception as error:
            self.errors += 1
            logger.error("sdk_record_failed type=%s", error.__class__.__name__)

    @contextmanager
    def span(self, type: str, attributes_factory: Callable[[], dict[str, Any]]) -> Iterator[None]:
        trace_id, parent = current_ids()
        trace_id, span_id = trace_id or str(uuid4()), str(uuid4())
        started_at, started = datetime.now(UTC), perf_counter()
        status = "ok"
        try:
            with span_scope(trace_id, span_id):
                yield
        except BaseException as error:
            status = "error"
            self.record_error(error, trace_id, span_id)
            raise
        finally:
            try:
                attributes = attributes_factory()
                self.record(
                    type,
                    attributes,
                    started_at=started_at,
                    duration_ms=(perf_counter() - started) * 1000,
                    status=status,
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent,
                )
            except Exception as error:
                logger.error("sdk_span_failed type=%s", error.__class__.__name__)

    def record_error(self, error: BaseException, trace_id: str, parent_span_id: str) -> None:
        try:
            message_hash = hash_payload(str(error))
        except Exception:
            message_hash = hash_payload(type(error).__name__)
        self.record(
            "error",
            {"exception_type": type(error).__name__, "message_hash": message_hash},
            started_at=datetime.now(UTC),
            duration_ms=0,
            status="error",
            trace_id=trace_id,
            parent_span_id=parent_span_id,
        )

    def _send(self, events: list[dict[str, Any]]) -> bool:
        batch_id = str(uuid4())
        for attempt in range(len(RETRY_DELAYS) + 1):
            result = self.transport.send(
                events, batch_id, {"dropped": self.spool.dropped, "spooled": self.spool.spooled}
            )
            if result is not SendResult.RETRYABLE:
                return True
            if attempt < len(RETRY_DELAYS) and not self._stop.is_set():
                self._stop.wait(RETRY_DELAYS[attempt])
        return False

    def _drain_spool(self) -> None:
        previous = None
        for path, events in self.spool.iter_batches(self.config.batch_size):
            if self._stop.is_set():
                return
            if previous is not None and previous != path:
                self.spool.commit(previous)
            if events and not self._send(events):
                return
            previous = path
        if previous is not None:
            self.spool.commit(previous)

    def _run_loop(self) -> None:
        pending: list[dict[str, Any]] = []
        interval = self.config.flush_interval_ms / 1000
        deadline = perf_counter() + interval
        while not self._stop.is_set():
            pending.extend(
                self.buffer.drain(
                    self.config.batch_size - len(pending), max(0, deadline - perf_counter())
                )
            )
            if len(pending) >= self.config.batch_size or perf_counter() >= deadline:
                self._persist(pending)
                pending = []
                deadline = perf_counter() + interval
        self._persist(pending)

    def _persist(self, events: list[dict[str, Any]]) -> None:
        try:
            self.spool.append(events)
        except OSError as error:
            self.errors += len(events)
            logger.error(
                "sdk_disk_write_failed type=%s lost_events=%s", type(error).__name__, len(events)
            )

    def _send_loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._drain_spool()
            except Exception as error:
                logger.error("sdk_send_failed type=%s", type(error).__name__)
            self._stop.wait(self.config.flush_interval_ms / 1000)

    def shutdown(self, timeout_s: float = 5) -> None:
        with self._lifecycle:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
        deadline = perf_counter() + timeout_s
        if self._thread:
            self._thread.join(max(0, deadline - perf_counter()))
        if self._sender:
            self._sender.join(max(0, deadline - perf_counter()))
        while events := self.buffer.drain(self.config.batch_size, 0):
            self.spool.append(events)
        if not self._sender or not self._sender.is_alive():
            self.transport.close()
