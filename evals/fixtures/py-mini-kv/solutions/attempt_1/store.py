"""KVStore (Attempt 1: straightforward dict + explicit checks)."""

from __future__ import annotations

import time
from typing import Callable, Optional

from ttl import compute_deadline, is_expired


class KVStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._values: dict[str, str] = {}
        self._deadlines: dict[str, Optional[float]] = {}

    def put(self, key: str, value: str, ttl_seconds: Optional[float] = None) -> None:
        if not key:
            raise ValueError("key must not be empty")
        if ttl_seconds is not None and ttl_seconds <= 0:
            self._values.pop(key, None)
            self._deadlines.pop(key, None)
            return
        self._values[key] = value
        self._deadlines[key] = compute_deadline(self._clock(), ttl_seconds)

    def get(self, key: str) -> Optional[str]:
        if key not in self._values:
            return None
        if is_expired(self._deadlines.get(key), self._clock()):
            self._values.pop(key, None)
            self._deadlines.pop(key, None)
            return None
        return self._values[key]

    def delete(self, key: str) -> bool:
        if key not in self._values:
            return False
        expired = is_expired(self._deadlines.get(key), self._clock())
        self._values.pop(key, None)
        self._deadlines.pop(key, None)
        return not expired

    def keys(self) -> list[str]:
        now = self._clock()
        active: list[str] = []
        for k in list(self._values.keys()):
            if is_expired(self._deadlines.get(k), now):
                self._values.pop(k, None)
                self._deadlines.pop(k, None)
            else:
                active.append(k)
        return sorted(active)
