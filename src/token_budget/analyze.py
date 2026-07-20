"""Pure aggregation: attribute usage to milestones, compute cost and metrics.

Given parsed UsageRecords, a Manifest, and the milestone Windows, produce a
BudgetReport with per-milestone token/cost/verdict rows, a cumulative total vs
the ceiling, a projection, and the saving metrics that tell us whether the
optimisation techniques are working (cache-hit ratio, output share, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from . import config
from .ledger import Manifest, Window
from .parse import UsageRecord


def _to_dt(iso: str) -> Optional[datetime]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _cost(record: UsageRecord) -> float:
    price = config.price_for(record.model)
    return (
        record.input * price["input"]
        + record.cache_read * price["cache_read"]
        + record.cache_write_5m * price["cache_write_5m"]
        + record.cache_write_1h * price["cache_write_1h"]
        + record.output * price["output"]
    ) / 1_000_000.0


@dataclass
class Bucket:
    input: int = 0
    cache_read: int = 0
    cache_write: int = 0
    output: int = 0
    cost: float = 0.0
    sidechain_tokens: int = 0

    def add(self, record: UsageRecord) -> None:
        self.input += record.input
        self.cache_read += record.cache_read
        self.cache_write += record.cache_write_5m + record.cache_write_1h
        self.output += record.output
        self.cost += _cost(record)
        if record.is_sidechain:
            self.sidechain_tokens += record.total

    @property
    def total(self) -> int:
        return self.input + self.cache_read + self.cache_write + self.output


def _attribute(records: List[UsageRecord], windows: List[Window]) -> dict[str, Bucket]:
    resolved = [(w, _to_dt(w.start), _to_dt(w.end)) for w in windows]
    buckets: dict[str, Bucket] = {}
    for record in records:
        moment = _to_dt(record.timestamp)
        target = "unattributed"
        if moment is not None:
            for window, start, end in resolved:
                if start is None:
                    continue
                if moment >= start and (end is None or moment <= end):
                    target = window.milestone
                    break
        buckets.setdefault(target, Bucket()).add(record)
    return buckets


@dataclass
class MilestoneRow:
    id: str
    title: str
    budget: int
    effort: str
    tokens: int
    cost: float
    fraction: float
    verdict: str
    dod_ok: bool


@dataclass
class BudgetReport:
    rows: List[MilestoneRow]
    unattributed: Bucket
    total_tokens: int
    total_cost: float
    ceiling: int
    ceiling_fraction: float
    ceiling_verdict: str
    projected_tokens: int
    cache_hit_ratio: float
    output_share: float
    subagent_share: float
    verdict_code: int  # 0 OK, 3 WARN, 4 OVER


def _verdict(tokens: int, budget: int, warn: float) -> str:
    if budget <= 0:
        return "OK"
    if tokens > budget:
        return "OVER"
    if tokens >= warn * budget:
        return "WARN"
    return "OK"


def build_report(records: Iterable[UsageRecord], manifest: Manifest,
                 windows: List[Window]) -> BudgetReport:
    records = list(records)
    buckets = _attribute(records, windows)
    window_by_id = {window.milestone: window for window in windows}
    warn = manifest.warn_fraction

    rows: List[MilestoneRow] = []
    done_ids: set[str] = set()
    projected = 0
    for milestone in manifest.milestones:
        bucket = buckets.get(milestone.id, Bucket())
        window = window_by_id.get(milestone.id)
        is_done = window is not None and window.end is not None
        if is_done:
            done_ids.add(milestone.id)
        fraction = (bucket.total / milestone.budget_tokens) if milestone.budget_tokens else 0.0
        rows.append(MilestoneRow(
            id=milestone.id,
            title=milestone.title,
            budget=milestone.budget_tokens,
            effort=milestone.effort,
            tokens=bucket.total,
            cost=bucket.cost,
            fraction=fraction,
            verdict=_verdict(bucket.total, milestone.budget_tokens, warn),
            dod_ok=(window.dod_ok if window else False),
        ))
        # Projection: done milestones count actuals; open ones count the
        # larger of actual-so-far and their remaining budget.
        projected += bucket.total if is_done else max(bucket.total, milestone.budget_tokens)

    unattributed = buckets.get("unattributed", Bucket())

    # The 8M budget tracks ATTRIBUTED milestone work only. The unattributed
    # bucket (prior / unrelated Claude Code sessions in the same transcript dir)
    # is reported separately and is NOT counted against the ceiling.
    attributed = [buckets.get(milestone.id, Bucket()) for milestone in manifest.milestones]
    total_tokens = sum(bucket.total for bucket in attributed)
    total_cost = sum(bucket.cost for bucket in attributed)

    aggregate = Bucket()
    for bucket in attributed:
        aggregate.input += bucket.input
        aggregate.cache_read += bucket.cache_read
        aggregate.cache_write += bucket.cache_write
        aggregate.output += bucket.output
        aggregate.sidechain_tokens += bucket.sidechain_tokens

    cache_denom = aggregate.input + aggregate.cache_read + aggregate.cache_write
    cache_hit_ratio = (aggregate.cache_read / cache_denom) if cache_denom else 0.0
    output_share = (aggregate.output / total_tokens) if total_tokens else 0.0
    subagent_share = (aggregate.sidechain_tokens / total_tokens) if total_tokens else 0.0

    ceiling = manifest.ceiling_tokens
    ceiling_fraction = (total_tokens / ceiling) if ceiling else 0.0
    if total_tokens > ceiling:
        ceiling_verdict = "OVER"
    elif total_tokens >= warn * ceiling or projected > ceiling:
        ceiling_verdict = "WARN"
    else:
        ceiling_verdict = "OK"

    if ceiling_verdict == "OVER" or any(row.verdict == "OVER" for row in rows):
        verdict_code = 4
    elif ceiling_verdict == "WARN" or any(row.verdict == "WARN" for row in rows):
        verdict_code = 3
    else:
        verdict_code = 0

    return BudgetReport(
        rows=rows,
        unattributed=unattributed,
        total_tokens=total_tokens,
        total_cost=total_cost,
        ceiling=ceiling,
        ceiling_fraction=ceiling_fraction,
        ceiling_verdict=ceiling_verdict,
        projected_tokens=projected,
        cache_hit_ratio=cache_hit_ratio,
        output_share=output_share,
        subagent_share=subagent_share,
        verdict_code=verdict_code,
    )
