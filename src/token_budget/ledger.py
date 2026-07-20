"""Budget manifest (committed) + mutable milestone ledger (start/done stamps).

The manifest defines milestones and their token budgets; the ledger records
when each milestone started and finished so usage can be attributed by time
window. Writing a stamp is the only I/O and is append-only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class MilestoneDef:
    id: str
    title: str
    budget_tokens: int
    effort: str


@dataclass(frozen=True)
class Manifest:
    ceiling_tokens: int
    warn_fraction: float
    project_cwd_substr: str
    milestones: tuple[MilestoneDef, ...]

    def by_id(self, milestone_id: str) -> Optional[MilestoneDef]:
        for milestone in self.milestones:
            if milestone.id == milestone_id:
                return milestone
        return None


def load_manifest(path: Path) -> Manifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    milestones = tuple(
        MilestoneDef(
            id=str(entry["id"]),
            title=str(entry.get("title", "")),
            budget_tokens=int(entry["budget_tokens"]),
            effort=str(entry.get("effort", "")),
        )
        for entry in data.get("milestones", [])
    )
    return Manifest(
        ceiling_tokens=int(data.get("ceiling_tokens", 8_000_000)),
        warn_fraction=float(data.get("warn_fraction", 0.8)),
        project_cwd_substr=str(data.get("project_cwd_substr", "")),
        milestones=milestones,
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_stamp(ledger_path: Path, milestone: str, event: str,
                 dod_ok: bool = True, at: Optional[str] = None) -> dict:
    stamp = {"milestone": milestone, "event": event, "at": at or now_iso(), "dod_ok": bool(dod_ok)}
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stamp) + "\n")
    return stamp


def read_stamps(ledger_path: Path) -> list[dict]:
    path = Path(ledger_path)
    if not path.exists():
        return []
    stamps: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            stamps.append(json.loads(line))
        except ValueError:
            continue
    return stamps


@dataclass(frozen=True)
class Window:
    milestone: str
    start: str
    end: Optional[str]
    dod_ok: bool


def build_windows(stamps: list[dict]) -> list[Window]:
    """Collapse start/done stamps into one [start, end] window per milestone."""
    starts: dict[str, str] = {}
    ends: dict[str, str] = {}
    dod: dict[str, bool] = {}
    for stamp in stamps:
        milestone = stamp.get("milestone")
        event = stamp.get("event")
        at = stamp.get("at")
        if not milestone or not at:
            continue
        if event == "start":
            if milestone not in starts or at < starts[milestone]:
                starts[milestone] = at
        elif event == "done":
            if milestone not in ends or at > ends[milestone]:
                ends[milestone] = at
            dod[milestone] = bool(stamp.get("dod_ok", True))
    windows = [
        Window(milestone, start, ends.get(milestone), dod.get(milestone, True))
        for milestone, start in starts.items()
    ]
    windows.sort(key=lambda window: window.start)
    return windows
