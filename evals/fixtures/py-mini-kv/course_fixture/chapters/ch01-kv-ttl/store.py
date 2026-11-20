"""In-memory KV store with lazy TTL eviction (starter stub)."""

from __future__ import annotations

import time
from typing import Callable, Optional


class KVStore:
    """In-memory key-value store supporting injectable clock and lazy TTL eviction."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock

    def put(self, key: str, value: str, ttl_seconds: Optional[float] = None) -> None:
        """Store key/value with optional TTL in seconds. Empty key raises ValueError."""
        raise NotImplementedError("TODO: put")

    def get(self, key: str) -> Optional[str]:
        """Return value if key exists and is not expired; otherwise None."""
        raise NotImplementedError("TODO: get")

    def delete(self, key: str) -> bool:
        """Delete key and return True if an active (non-expired) key was removed."""
        raise NotImplementedError("TODO: delete")

    def keys(self) -> list[str]:
        """Return sorted list of all currently non-expired keys."""
        raise NotImplementedError("TODO: keys")
