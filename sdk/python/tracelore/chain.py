from threading import Lock
from typing import Any

from .canonical import compute_event_hash

GENESIS_HASH = "0" * 64


class HashChain:
    def __init__(self, stream_id: str) -> None:
        self.stream_id = stream_id
        self._sequence = 0
        self._last_hash = GENESIS_HASH
        self._lock = Lock()

    def seal(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            sealed = event.copy()
            self._sequence += 1
            sealed.update(
                stream_id=self.stream_id, sequence=self._sequence, prev_event_hash=self._last_hash
            )
            sealed["event_hash"] = compute_event_hash(sealed)
            self._last_hash = sealed["event_hash"]
            return sealed
