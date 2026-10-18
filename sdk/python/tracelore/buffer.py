from queue import Empty, Full, Queue
from threading import Lock
from typing import Any


class EventBuffer:
    def __init__(self, max_size: int) -> None:
        self._queue: Queue[dict[str, Any]] = Queue(maxsize=max_size)
        self._dropped = 0
        self._lock = Lock()

    def put(self, event: dict[str, Any]) -> bool:
        try:
            self._queue.put_nowait(event)
            return True
        except Full:
            with self._lock:
                self._dropped += 1
            return False

    def drain(self, max_items: int, timeout_s: float) -> list[dict[str, Any]]:
        try:
            items = [self._queue.get(timeout=timeout_s)]
        except Empty:
            return []
        for _ in range(max_items - 1):
            try:
                items.append(self._queue.get_nowait())
            except Empty:
                break
        return items

    @property
    def dropped(self) -> int:
        return self._dropped
