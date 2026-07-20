"""token_budget - track Claude Code token spend against a milestone budget.

Standard library only. Reads Claude Code JSONL transcripts, attributes token
usage to milestones by time window, computes cost from a pricing table, and
enforces a hard ceiling (8M tokens) with warn/over gates.
"""

__version__ = "0.1.0"
