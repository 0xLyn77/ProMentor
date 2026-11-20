"""TTL expiration helpers (starter stub)."""

from __future__ import annotations

from typing import Optional


def compute_deadline(now: float, ttl_seconds: Optional[float]) -> Optional[float]:
    """Compute absolute expiration timestamp; None if no TTL."""
    raise NotImplementedError("TODO: compute_deadline")


def is_expired(expires_at: Optional[float], now: float) -> bool:
    """Return True if expires_at is set and now >= expires_at."""
    raise NotImplementedError("TODO: is_expired")
