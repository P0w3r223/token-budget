from token_budget.analyze import build_report
from token_budget.ledger import Manifest, MilestoneDef, Window
from token_budget.parse import UsageRecord


def _rec(ts, **kw):
    base = dict(timestamp=ts, session_id="s", model="claude-opus-4-8", is_sidechain=False,
                cwd="", input=0, cache_read=0, cache_write_5m=0, cache_write_1h=0, output=0)
    base.update(kw)
    return UsageRecord(**base)


MANIFEST = Manifest(
    ceiling_tokens=8_000_000, warn_fraction=0.8, project_cwd_substr="BIAP",
    milestones=(MilestoneDef("M1", "one", 400_000, "medium"),
                MilestoneDef("M2", "two", 500_000, "medium")),
)


def test_attribution_cost_and_verdict():
    records = [
        _rec("2026-07-20T10:00:00+00:00", input=1000, cache_read=10000, cache_write_5m=2000, output=500),
        _rec("2026-07-20T12:30:00+00:00", input=100, output=100),
    ]
    windows = [
        Window("M1", "2026-07-20T09:00:00+00:00", "2026-07-20T11:00:00+00:00", True),
        Window("M2", "2026-07-20T12:00:00+00:00", None, False),
    ]
    report = build_report(records, MANIFEST, windows)
    m1 = next(r for r in report.rows if r.id == "M1")
    m2 = next(r for r in report.rows if r.id == "M2")
    # cost = (1000*5 + 10000*0.5 + 2000*6.25 + 500*25) / 1e6 = 0.035
    assert m1.tokens == 13500
    assert abs(m1.cost - 0.035) < 1e-9
    assert m1.verdict == "OK"
    assert m2.tokens == 200
    assert report.total_tokens == 13700
    assert report.unattributed.total == 0
    assert report.verdict_code == 0


def test_over_budget_and_ceiling_gate():
    tiny = Manifest(ceiling_tokens=10_000, warn_fraction=0.8, project_cwd_substr="",
                    milestones=(MilestoneDef("M1", "one", 5_000, "medium"),))
    records = [_rec("2026-07-20T10:00:00+00:00", input=20000)]
    windows = [Window("M1", "2026-07-20T09:00:00+00:00", None, False)]
    report = build_report(records, tiny, windows)
    assert report.rows[0].verdict == "OVER"
    assert report.ceiling_verdict == "OVER"
    assert report.verdict_code == 4


def test_unattributed_when_no_window():
    records = [_rec("2026-07-20T10:00:00+00:00", input=1000)]
    report = build_report(records, MANIFEST, windows=[])
    assert report.unattributed.total == 1000
    assert all(row.tokens == 0 for row in report.rows)
