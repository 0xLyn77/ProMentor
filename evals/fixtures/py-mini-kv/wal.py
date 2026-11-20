"""Minimal append-only Write-Ahead Log (WAL) codec."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class WalRecord:
    op: str
    key: str
    value: Optional[str] = None


def encode_record(record: WalRecord) -> str:
    """Serialize a WAL record as a single JSON line."""
    if record.op not in ("PUT", "DEL"):
        raise ValueError(f"unsupported op: {record.op}")
    return json.dumps({"op": record.op, "key": record.key, "value": record.value}, separators=(",", ":"))


def decode_record(line: str) -> WalRecord:
    """Deserialize a single JSON line into a WalRecord."""
    payload = json.loads(line)
    op = payload["op"]
    if op not in ("PUT", "DEL"):
        raise ValueError(f"unsupported op: {op}")
    return WalRecord(op=op, key=payload["key"], value=payload.get("value"))


def replay_records(lines: Iterable[str]) -> dict[str, str]:
    """Replay serialized WAL lines into final key-value state."""
    state: dict[str, str] = {}
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        rec = decode_record(stripped)
        if rec.op == "PUT" and rec.value is not None:
            state[rec.key] = rec.value
        elif rec.op == "DEL":
            state.pop(rec.key, None)
    return state
