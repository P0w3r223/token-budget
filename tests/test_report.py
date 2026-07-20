from token_budget.analyze import build_report
from token_budget.ledger import Manifest, MilestoneDef, Window
from token_budget.parse import UsageRecord
from token_budget.report import render_quiet, render_terminal, to_json_dict


def _report():
    manifest = Manifest(8_000_000, 0.8, "BIAP", (MilestoneDef("M1", "one", 400_000, "medium"),))
    record = UsageRecord("2026-07-20T10:00:00+00:00", "s", "claude-opus-4-8", False, "",
                         1000, 10000, 2000, 0, 500)
    windows = [Window("M1", "2026-07-20T09:00:00+00:00", None, False)]
    return build_report([record], manifest, windows)


def test_quiet_line_has_key_fields():
    line = render_quiet(_report())
    assert "M1" in line
    assert "total" in line
    assert "cache-hit" in line


def test_terminal_is_ascii_only():
    text = render_terminal(_report())
    text.encode("ascii")  # must not raise
    assert "TOKEN BUDGET" in text
    assert "SAVING METRICS" in text


def test_json_dict_keys_and_totals():
    data = to_json_dict(_report())
    assert data["total_tokens"] == 13500
    assert data["milestones"][0]["id"] == "M1"
    assert "cache_hit_ratio" in data
    assert data["verdict_code"] == 0
