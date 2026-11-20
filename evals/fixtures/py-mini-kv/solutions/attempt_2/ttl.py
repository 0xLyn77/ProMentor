"""TTL expiration helpers (Attempt 2)."""

from __future__ import annotations

from typing import Optional


def compute_deadline(now: float, ttl_seconds: Optional[float]) -> Optional[float]:
    return None if ttl_seconds is None else now + ttl_seconds


def is_expired(expires_at: Optional[float], now: float) -> bool:
    return expires_at is not None and now >= expires_at
