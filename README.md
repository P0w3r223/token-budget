# token-budget

[![CI](https://github.com/P0w3r223/token-budget/actions/workflows/ci.yml/badge.svg)](https://github.com/P0w3r223/token-budget/actions/workflows/ci.yml)

Standard-library-only CLI that measures **Claude Code** token spend against a
milestone budget and enforces a hard ceiling. Portfolio project **A6** — built
after measuring the true, cache-read-dominated cost of agentic coding.

## Why

Claude Code bills mostly **cache-read** tokens (the growing context is re-sent
every turn) — in real transcripts ~97% of total tokens, while output tokens
(~0.5%) drive the dollar cost at $25/M. The `/cost` view shows a live number but
nothing is persisted and nothing ties spend to a plan. `token-budget` reads the
JSONL transcripts Claude Code already writes, attributes usage to your
milestones, and gates the build so a token budget is actually enforceable.

## What it does

- Streams `~/.claude/projects/*/*.jsonl` (incl. sub-agent files) and reads
  `message.usage` per assistant turn (input, cache-read, cache-write 5m/1h, output).
- Attributes usage to milestones by time window (from `start`/`done` stamps).
- Computes cost from a per-model pricing table (Opus / Sonnet / Haiku).
- Reports **saving metrics**: cache-hit ratio, output share, subagent share,
  projected total.
- Exit codes gate CI/hooks: `0` OK, `3` WARN (>=80%), `4` OVER.

## Install

```bash
pip install -e .          # add [dev] for the test extra: pip install -e ".[dev]"
```

## Usage

Put a `budget.json` in your project (copy `budget.example.json`):

```json
{
  "ceiling_tokens": 8000000,
  "warn_fraction": 0.8,
  "project_cwd_substr": "my-project",
  "milestones": [
    {"id": "M1", "title": "Core", "budget_tokens": 4000000, "effort": "medium"}
  ]
}
```

```bash
token-budget start M1        # stamp a milestone start
token-budget report          # full dashboard (also --json / --quiet)
token-budget status          # one-line status
token-budget done M1         # stamp end + PASS / OVER vs its budget
```

The budget counts **attributed** milestone tokens only; unrelated prior sessions
in the same transcript dir are reported as "unattributed", never against the
ceiling. `--manifest`, `--state-dir`, `--transcripts-dir` and `--no-cwd-filter`
override the defaults.

## Sample output

```
TOKEN BUDGET - studia-rag
==========================================================================
ID   Milestone                          Effort     Tokens   Budget     % Verdict
--------------------------------------------------------------------------
M1   Core                               medium      1.30M    4.00M   33%      OK
--------------------------------------------------------------------------
CUMULATIVE  1.30M / 8.00M  (16%)  -> OK
Projected total (spent + remaining budgets): 4.00M
Estimated cost: $2.10

SAVING METRICS
  cache-hit ratio : 88%   (target >=85%)
  output share    : 4%    (cost-weighted driver)
  subagent share  : 0%
```

## Saving metrics

| Metric | Meaning | Target |
|---|---|---|
| cache-hit ratio | cache-read / (input + cache-read + cache-write) | >=85% |
| output share | output tokens / total (the $ driver at $25/M) | low |
| subagent share | sidechain tokens / total | watch |
| projected total | spent + remaining milestone budgets | <= ceiling |

## Limitations

- Attribution is by wall-clock window; overlapping sessions in one window are
  summed together. Cost is an estimate from the bundled pricing table — update it
  on price changes. The cwd pre-filter is coarse; `--no-cwd-filter` scans every
  transcript.

## Development

```bash
pip install -e ".[dev]"
pytest
```

MIT licensed.
