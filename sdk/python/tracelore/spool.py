import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from threading import Lock
from time import time_ns
from typing import Any
from uuid import uuid4

from .canonical import canonical_json

logger = logging.getLogger(__name__)
SEGMENT_BYTES = 5 * 1024 * 1024


class Spool:
    def __init__(self, directory: Path, max_mb: float) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._limit = int(max_mb * 1024 * 1024)
        self._lock = Lock()
        self._active: Path | None = None
        self.spooled = 0
        self.dropped = 0

    def append(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        data = b"".join(canonical_json(event) + b"\n" for event in events)
        with self._lock:
            if self._active is None or not self._active.exists():
                self._active = self.directory / f"spool-{time_ns()}-{uuid4().hex}.jsonl"
            elif self._active.stat().st_size + len(data) > SEGMENT_BYTES:
                self._active = self.directory / f"spool-{time_ns()}-{uuid4().hex}.jsonl"
            with self._active.open("ab") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self.spooled += len(events)
            self._trim()

    def _trim(self) -> None:
        files = sorted(self.directory.glob("spool-*"))
        total = sum(path.stat().st_size for path in files if path.exists())
        for path in files:
            if total <= self._limit:
                return
            if path.exists():
                data = path.read_bytes()
                total -= len(data)
                self.dropped += data.count(b"\n")
                path.unlink(missing_ok=True)
                logger.warning("spool_limit_exceeded dropped=%s", self.dropped)

    def iter_batches(self, batch_size: int) -> Iterator[tuple[Path, list[dict[str, Any]]]]:
        for path in self._claim():
            items: list[dict[str, Any]] = []
            if not path.exists():
                continue
            for line in path.read_bytes().splitlines(keepends=True):
                if not line.endswith(b"\n"):
                    logger.warning("truncated_spool_line segment=%s", path.name)
                    continue
                try:
                    items.append(json.loads(line))
                except (ValueError, UnicodeDecodeError):
                    logger.error("corrupt_spool_line segment=%s", path.name)
                    continue
                if len(items) == batch_size:
                    yield path, items
                    items = []
            yield path, items

    def _claim(self) -> list[Path]:
        with self._lock:
            self._active = None
            for path in self.directory.glob("spool-*.jsonl"):
                try:
                    path.replace(path.with_suffix(".sending"))
                except FileNotFoundError:
                    logger.debug("spool_claimed_by_peer segment=%s", path.name)
            return sorted(self.directory.glob("spool-*.sending"))

    def commit(self, segment_path: Path) -> None:
        if segment_path.parent.resolve() != self.directory.resolve():
            raise ValueError("segment is outside spool directory")
        segment_path.unlink(missing_ok=True)
