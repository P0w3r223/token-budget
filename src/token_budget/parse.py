"""Pure parsing of Claude Code JSONL transcript lines into UsageRecord rows.

No I/O here: callers pass an iterable of raw lines. Non-assistant lines,
lines without a usage object, and malformed JSON are silently skipped so the
tracker never crashes on a partial or corrupt transcript.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional


@dataclass(frozen=True)
class UsageRecord:
    timestamp: str
    session_id: str
    model: str
    is_sidechain: bool
    cwd: str
    input: int
    cache_read: int
    cache_write_5m: int
    cache_write_1h: int
    output: int

    @property
    def total(self) -> int:
        return (
            self.input
            + self.cache_read
            + self.cache_write_5m
            + self.cache_write_1h
            + self.output
        )


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _record_from_obj(obj: dict) -> Optional[UsageRecord]:
    if obj.get("type") != "assistant":
        return None
    message = obj.get("message") or {}
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    cache_creation = usage.get("cache_creation") or {}
    write_5m = _int(cache_creation.get("ephemeral_5m_input_tokens"))
    write_1h = _int(cache_creation.get("ephemeral_1h_input_tokens"))
    if write_5m == 0 and write_1h == 0:
        # Older/flat shape: no 5m/1h split. Treat as 5m (the default TTL).
        write_5m = _int(usage.get("cache_creation_input_tokens"))
    return UsageRecord(
        timestamp=str(obj.get("timestamp", "")),
        session_id=str(obj.get("sessionId", "")),
        model=str(message.get("model", "")),
        is_sidechain=bool(obj.get("isSidechain", False)),
        cwd=str(obj.get("cwd", "")),
        input=_int(usage.get("input_tokens")),
        cache_read=_int(usage.get("cache_read_input_tokens")),
        cache_write_5m=write_5m,
        cache_write_1h=write_1h,
        output=_int(usage.get("output_tokens")),
    )


def records_from_lines(lines: Iterable[str]) -> Iterator[UsageRecord]:
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        record = _record_from_obj(obj)
        if record is not None:
            yield record
