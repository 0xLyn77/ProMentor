"""Minimal in-memory key-value store with TTL expiration."""

from __future__ import annotations

import time
from typing import Callable, Optional


class KVStore:
    """In-memory key-value store supporting lazy TTL eviction."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._data: dict[str, tuple[str, Optional[float]]] = {}

    def put(self, key: str, value: str, ttl_seconds: Optional[float] = None) -> None:
        if not key:
            raise ValueError("key must not be empty")
        if ttl_seconds is not None and ttl_seconds <= 0:
            self._data.pop(key, None)
            return
        expires_at = None if ttl_seconds is None else self._clock() + ttl_seconds
        self._data[key] = (value, expires_at)

    def get(self, key: str) -> Optional[str]:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and self._clock() >= expires_at:
            self._data.pop(key, None)
            return None
        return value

    def delete(self, key: str) -> bool:
        entry = self._data.get(key)
        if entry is None:
            return False
        _, expires_at = entry
        self._data.pop(key, None)
        if expires_at is not None and self._clock() >= expires_at:
            return False
        return True

    def keys(self) -> list[str]:
        now = self._clock()
        expired = [k for k, (_, exp) in self._data.items() if exp is not None and now >= exp]
        for k in expired:
            self._data.pop(k, None)
        return sorted(self._data.keys())
