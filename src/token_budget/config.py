"""Constants + path resolution. No transcript I/O here.

Pricing (USD per 1,000,000 tokens) keyed by model id, plus helpers that resolve
the budget manifest and the mutable ledger relative to the current working
directory so the tool works inside any project. cache_read is 0.1x input,
cache_write_5m is 1.25x input, cache_write_1h is 2.0x input.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-8":   {"input": 5.0, "output": 25.0, "cache_read": 0.5, "cache_write_5m": 6.25, "cache_write_1h": 10.0},
    "claude-opus-4-7":   {"input": 5.0, "output": 25.0, "cache_read": 0.5, "cache_write_5m": 6.25, "cache_write_1h": 10.0},
    "claude-sonnet-5":   {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write_5m": 3.75, "cache_write_1h": 6.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write_5m": 3.75, "cache_write_1h": 6.0},
    "claude-haiku-4-5":  {"input": 1.0, "output": 5.0,  "cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2.0},
}
_DEFAULT_MODEL = "claude-opus-4-8"


def price_for(model: Optional[str]) -> dict[str, float]:
    """Pricing for a model id (exact, then prefix, then Opus fallback)."""
    if model:
        if model in PRICING:
            return PRICING[model]
        for key in PRICING:
            if model.startswith(key):
                return PRICING[key]
    return PRICING[_DEFAULT_MODEL]


def default_transcript_dirs() -> list[Path]:
    """Where Claude Code writes its per-session JSONL transcripts."""
    return [Path.home() / ".claude" / "projects"]


DEFAULT_MANIFEST_NAME = "budget.json"
DEFAULT_STATE_DIRNAME = ".token-budget"
# src/token_budget/config.py -> repo root is three parents up.
_BUNDLED_EXAMPLE = Path(__file__).resolve().parent.parent.parent / "budget.example.json"


def resolve_manifest(explicit: Optional[str]) -> Path:
    """Manifest to use: explicit flag, else ./budget.json, else bundled example."""
    if explicit:
        return Path(explicit)
    cwd_manifest = Path.cwd() / DEFAULT_MANIFEST_NAME
    if cwd_manifest.exists():
        return cwd_manifest
    return _BUNDLED_EXAMPLE


def resolve_state_dir(explicit: Optional[str]) -> Path:
    """Directory holding the mutable ledger (default: ./.token-budget)."""
    if explicit:
        return Path(explicit)
    return Path.cwd() / DEFAULT_STATE_DIRNAME
