"""I/O boundary: transcript discovery, argparse subcommands, exit codes.

Exit codes double as gates: 0 OK, 2 bad args, 3 WARN (>=80% of a budget),
4 OVER (a milestone or the ceiling exceeded), 1 internal error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Iterator, Optional

from . import config
from .analyze import build_report
from .ledger import append_stamp, build_windows, load_manifest, read_stamps
from .parse import records_from_lines
from .report import render_quiet, render_terminal, to_json_dict

EXIT_OK, EXIT_ERR, EXIT_ARGS, EXIT_WARN, EXIT_OVER = 0, 1, 2, 3, 4


def _iter_transcript_files(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        path = Path(path)
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from sorted(path.rglob("*.jsonl"))


def _iter_lines(files: Iterable[Path], cwd_substr: Optional[str]) -> Iterator[str]:
    for file in files:
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if cwd_substr and cwd_substr not in text:
            continue  # coarse pre-filter; time-window attribution does the rest
        yield from text.splitlines()


def _load_records(args, manifest):
    if args.transcripts_dir:
        dirs = [Path(p) for p in args.transcripts_dir]
    else:
        dirs = config.default_transcript_dirs()
    if args.no_cwd_filter:
        cwd_substr = None
    else:
        cwd_substr = args.cwd_substr or manifest.project_cwd_substr or None
    return records_from_lines(_iter_lines(_iter_transcript_files(dirs), cwd_substr))


def _cmd_start(args, manifest) -> int:
    if manifest.by_id(args.milestone) is None:
        print(f"warn: '{args.milestone}' is not in the manifest", file=sys.stderr)
    stamp = append_stamp(args.ledger_path, args.milestone, "start")
    print(f"START {args.milestone} @ {stamp['at']}")
    return EXIT_OK


def _cmd_done(args, manifest) -> int:
    dod_ok = not args.fail
    append_stamp(args.ledger_path, args.milestone, "done", dod_ok=dod_ok)
    windows = build_windows(read_stamps(args.ledger_path))
    report = build_report(_load_records(args, manifest), manifest, windows)
    row = next((r for r in report.rows if r.id == args.milestone), None)
    if row is None:
        print(f"DONE {args.milestone} (not in manifest)")
        return EXIT_OK
    if row.verdict == "OVER":
        status, code = "OVER-BUDGET", EXIT_OVER
    elif not dod_ok:
        status, code = "DOD-FAIL", EXIT_ERR
    else:
        status, code = "PASS", EXIT_OK
    print(f"DONE {args.milestone}: {row.tokens / 1e6:.2f}M/{row.budget / 1e6:.2f}M "
          f"({row.fraction * 100:.0f}%) -> {status}")
    return code


def _cmd_report(args, manifest) -> int:
    windows = build_windows(read_stamps(args.ledger_path))
    report = build_report(_load_records(args, manifest), manifest, windows)
    if getattr(args, "json", False):
        print(json.dumps(to_json_dict(report), indent=2))
    elif getattr(args, "quiet", False):
        print(render_quiet(report))
    else:
        print(render_terminal(report))
    return report.verdict_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="token-budget",
        description="Track Claude Code token spend against a milestone budget.",
    )
    parser.add_argument("--manifest", default=None,
                        help="budget manifest JSON (default: ./budget.json, else bundled example)")
    parser.add_argument("--state-dir", default=None,
                        help="directory for the mutable ledger (default: ./.token-budget)")
    parser.add_argument("--transcripts-dir", action="append", default=None,
                        help="transcript dir or .jsonl file (repeatable)")
    parser.add_argument("--cwd-substr", default=None,
                        help="override the project cwd pre-filter substring")
    parser.add_argument("--no-cwd-filter", action="store_true",
                        help="disable the cwd pre-filter (scan every transcript)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start", help="stamp the start of a milestone")
    start.add_argument("milestone")

    done = sub.add_parser("done", help="stamp the end of a milestone and check its budget")
    done.add_argument("milestone")
    done.add_argument("--fail", action="store_true", help="mark the definition-of-done as not met")

    report = sub.add_parser("report", help="full budget dashboard")
    report.add_argument("--json", action="store_true")
    report.add_argument("--quiet", action="store_true")

    sub.add_parser("status", help="one-line budget status (alias for report --quiet)")
    return parser


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    args = build_parser().parse_args(argv)
    args.ledger_path = config.resolve_state_dir(args.state_dir) / "ledger.jsonl"
    try:
        manifest = load_manifest(config.resolve_manifest(args.manifest))
    except (OSError, ValueError) as error:
        print(f"error: cannot load manifest: {error}", file=sys.stderr)
        return EXIT_ERR

    if args.cmd == "start":
        return _cmd_start(args, manifest)
    if args.cmd == "done":
        return _cmd_done(args, manifest)
    if args.cmd == "status":
        args.quiet = True
        args.json = False
    return _cmd_report(args, manifest)
