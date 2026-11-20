"""TTL expiration helpers (Attempt 1)."""

from __future__ import annotations

from typing import Optional


def compute_deadline(now: float, ttl_seconds: Optional[float]) -> Optional[float]:
    if ttl_seconds is None:
        return None
    return now + ttl_seconds


def is_expired(expires_at: Optional[float], now: float) -> bool:
    if expires_at is None:
        return False
    return now >= expires_at
