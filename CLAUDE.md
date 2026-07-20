# CLAUDE.md — token-budget

Guidance for Claude Code (and any contributor) working in this repo.

## What this project is

Portfolio project **A6**. A standard-library-only CLI that tracks **Claude Code**
token spend against a milestone budget: it parses Claude Code's JSONL session
transcripts, attributes token usage to milestones by time window, computes cost
from a per-model pricing table, and enforces a hard ceiling with warn/over gates.
Born out of measuring the true (cache-read-dominated) cost of agentic coding.

## Architecture

```
src/token_budget/
  config.py    # pricing table + manifest/ledger path resolution (no transcript I/O)
  parse.py     # pure: JSONL lines -> UsageRecord (skips non-assistant/malformed)
  ledger.py    # manifest (budget.json) + mutable start/done stamps + windows
  analyze.py   # pure: attribute usage to milestones, cost + saving metrics
  report.py    # pure rendering: terminal dashboard, --json, quiet one-liner
  cli.py       # the only I/O: argparse, transcript discovery, exit codes
  __main__.py  # python -m token_budget
```

## Rules (do not violate)

- **Standard library only** at runtime — no third-party dependencies, ever.
- **Cost is never read from transcripts** (it is not stored there); always compute
  it from `config.PRICING` keyed by `message.model`.
- **The budget counts attributed milestone tokens only.** Prior/unrelated sessions
  in the same transcript dir are reported as "unattributed", never against the ceiling.
- **Pure core, quarantined I/O** — parse/analyze/report stay pure and unit-tested;
  transcript/file reads live only in `cli.py`.
- **ASCII-only rendered output** (safe on Windows cp1250 consoles).

## Conventions

English for code, comments, README, commits. Conventional Commits, work on
branches + PRs with a "why". No hardcoded values — pricing/thresholds live in
`config.py` / `budget.json`. Interpreter: `.venv/Scripts/python.exe` (Python 3.12).

## How to run

```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev]"
pytest
python -m token_budget report            # dashboard for the cwd's budget.json
python -m token_budget start M1          # stamp a milestone start
python -m token_budget done M1           # stamp end + PASS/OVER vs budget
```
