import json

from token_budget.cli import main

MANIFEST = {
    "ceiling_tokens": 8000000, "warn_fraction": 0.8, "project_cwd_substr": "BIAP",
    "milestones": [{"id": "M1", "title": "one", "budget_tokens": 400000, "effort": "medium"}],
}
LINE = (
    '{"type":"assistant","timestamp":"2026-07-20T10:00:00Z","sessionId":"s",'
    '"isSidechain":false,"cwd":"C:/x/BIAP","message":{"model":"claude-opus-4-8",'
    '"usage":{"input_tokens":1000,"cache_read_input_tokens":10000,"output_tokens":500,'
    '"cache_creation":{"ephemeral_5m_input_tokens":2000,"ephemeral_1h_input_tokens":0}}}}'
)


def _setup(tmp_path, manifest=MANIFEST):
    manifest_path = tmp_path / "budget.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    # Seed an open M1 window at 09:00 so the 10:00 transcript record attributes
    # to M1 (the ceiling total counts attributed milestone tokens only).
    (state_dir / "ledger.jsonl").write_text(
        json.dumps({"milestone": "M1", "event": "start",
                    "at": "2026-07-20T09:00:00+00:00", "dod_ok": True}) + "\n",
        encoding="utf-8",
    )
    transcript = tmp_path / "s.jsonl"
    transcript.write_text(LINE + "\n", encoding="utf-8")
    return manifest_path, state_dir, transcript


def _common(manifest_path, state_dir, transcript):
    return ["--manifest", str(manifest_path), "--state-dir", str(state_dir),
            "--no-cwd-filter", "--transcripts-dir", str(transcript)]


def test_report_json(tmp_path, capsys):
    manifest_path, state_dir, transcript = _setup(tmp_path)
    code = main(_common(manifest_path, state_dir, transcript) + ["report", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["total_tokens"] == 13500
    assert code == 0


def test_start_then_done(tmp_path, capsys):
    manifest_path, state_dir, transcript = _setup(tmp_path)
    assert main(["--manifest", str(manifest_path), "--state-dir", str(state_dir), "start", "M1"]) == 0
    code = main(_common(manifest_path, state_dir, transcript) + ["done", "M1"])
    assert "DONE M1" in capsys.readouterr().out
    assert code == 0


def test_ceiling_over_returns_exit_4(tmp_path, capsys):
    manifest = dict(MANIFEST)
    manifest["ceiling_tokens"] = 1000
    manifest_path, state_dir, transcript = _setup(tmp_path, manifest)
    code = main(_common(manifest_path, state_dir, transcript) + ["report"])
    assert code == 4


def test_uses_bundled_example_when_no_manifest(tmp_path, monkeypatch, capsys):
    # No ./budget.json in cwd -> falls back to the bundled budget.example.json.
    monkeypatch.chdir(tmp_path)
    code = main(["--no-cwd-filter", "--transcripts-dir", str(tmp_path / "none.jsonl"), "report"])
    assert "TOKEN BUDGET" in capsys.readouterr().out
    assert code in (0, 3, 4)
