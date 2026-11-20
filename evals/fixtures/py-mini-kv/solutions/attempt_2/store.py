"""KVStore (Attempt 2: unified single-table entry storage)."""

from __future__ import annotations

import time
from typing import Callable, Optional

from ttl import compute_deadline, is_expired


class KVStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[str, Optional[float]]] = {}

    def put(self, key: str, value: str, ttl_seconds: Optional[float] = None) -> None:
        if not key:
            raise ValueError("key must not be empty")
        if ttl_seconds is not None and ttl_seconds <= 0:
            self._entries.pop(key, None)
            return
        self._entries[key] = (value, compute_deadline(self._clock(), ttl_seconds))

    def get(self, key: str) -> Optional[str]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, deadline = entry
        if is_expired(deadline, self._clock()):
            self._entries.pop(key, None)
            return None
        return value

    def delete(self, key: str) -> bool:
        entry = self._entries.pop(key, None)
        if entry is None:
            return False
        _, deadline = entry
        return not is_expired(deadline, self._clock())

    def keys(self) -> list[str]:
        now = self._clock()
        expired = [k for k, (_, d) in self._entries.items() if is_expired(d, now)]
        for k in expired:
            self._entries.pop(k, None)
        return sorted(self._entries.keys())
