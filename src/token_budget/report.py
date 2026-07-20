"""Pure rendering of a BudgetReport. ASCII-only output (safe on cp1250 consoles).

Three renderers: a full terminal dashboard, a JSON dict for --json, and a
one-line status for the Stop hook.
"""
from __future__ import annotations

from .analyze import BudgetReport


def _m(tokens: int) -> str:
    return f"{tokens / 1_000_000:.2f}M"


def _pct(fraction: float) -> str:
    return f"{fraction * 100:.0f}%"


def render_quiet(report: BudgetReport) -> str:
    active = None
    for row in report.rows:
        if row.tokens > 0 and not row.dod_ok:
            active = row
    if active is None:
        for row in report.rows:
            if row.tokens > 0:
                active = row
    parts = []
    if active is not None:
        parts.append(f"{active.id} {_m(active.tokens)}/{_m(active.budget)} ({_pct(active.fraction)})")
    parts.append(f"total {_m(report.total_tokens)}/{_m(report.ceiling)} ({_pct(report.ceiling_fraction)})")
    parts.append(f"cache-hit {_pct(report.cache_hit_ratio)}")
    parts.append(report.ceiling_verdict)
    return " | ".join(parts)


def render_terminal(report: BudgetReport) -> str:
    width = 74
    lines = ["TOKEN BUDGET - studia-rag", "=" * width]
    lines.append(f"{'ID':<4} {'Milestone':<34} {'Effort':<7} {'Tokens':>9} {'Budget':>8} {'%':>5} {'Verdict':>7}")
    lines.append("-" * width)
    for row in report.rows:
        lines.append(
            f"{row.id:<4} {row.title[:34]:<34} {row.effort:<7} "
            f"{_m(row.tokens):>9} {_m(row.budget):>8} {_pct(row.fraction):>5} {row.verdict:>7}"
        )
    if report.unattributed.total > 0:
        lines.append(f"{'-':<4} {'(unattributed)':<34} {'':<7} {_m(report.unattributed.total):>9} {'':>8} {'':>5} {'':>7}")
    lines.append("-" * width)
    lines.append(
        f"CUMULATIVE  {_m(report.total_tokens)} / {_m(report.ceiling)}  "
        f"({_pct(report.ceiling_fraction)})  -> {report.ceiling_verdict}"
    )
    lines.append(f"Projected total (spent + remaining budgets): {_m(report.projected_tokens)}")
    lines.append(f"Estimated cost: ${report.total_cost:.2f}")
    lines.append("")
    lines.append("SAVING METRICS")
    lines.append(f"  cache-hit ratio : {_pct(report.cache_hit_ratio)}   (target >=85%)")
    lines.append(f"  output share    : {_pct(report.output_share)}   (cost-weighted driver)")
    lines.append(f"  subagent share  : {_pct(report.subagent_share)}")
    return "\n".join(lines)


def to_json_dict(report: BudgetReport) -> dict:
    return {
        "milestones": [
            {
                "id": row.id, "title": row.title, "effort": row.effort,
                "budget_tokens": row.budget, "tokens": row.tokens,
                "cost_usd": round(row.cost, 4), "fraction": round(row.fraction, 4),
                "verdict": row.verdict, "dod_ok": row.dod_ok,
            }
            for row in report.rows
        ],
        "unattributed_tokens": report.unattributed.total,
        "total_tokens": report.total_tokens,
        "total_cost_usd": round(report.total_cost, 4),
        "ceiling_tokens": report.ceiling,
        "ceiling_fraction": round(report.ceiling_fraction, 4),
        "ceiling_verdict": report.ceiling_verdict,
        "projected_tokens": report.projected_tokens,
        "cache_hit_ratio": round(report.cache_hit_ratio, 4),
        "output_share": round(report.output_share, 4),
        "subagent_share": round(report.subagent_share, 4),
        "verdict_code": report.verdict_code,
    }
