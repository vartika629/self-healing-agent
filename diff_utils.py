"""
diff_utils.py - Shows what changed between two versions of the code.

Uses Python's built-in `difflib` (the same idea that `git diff` uses).
Lines starting with "+" were added, lines starting with "-" were removed.
"""

from __future__ import annotations

import difflib


def make_diff(old: str, new: str, old_name: str = "before", new_name: str = "after") -> str:
    """Return a unified diff (like `git diff`) as a string. Empty if no change."""
    lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=old_name,
        tofile=new_name,
        n=2,  # lines of context around each change
    )
    out = "".join(lines)
    return out if out.endswith("\n") or not out else out + "\n"


def diff_stats(old: str, new: str) -> tuple[int, int]:
    """Count (lines_added, lines_removed)."""
    added = removed = 0
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added, removed


def similarity(old: str, new: str) -> float:
    """0.0 = completely different, 1.0 = identical."""
    return difflib.SequenceMatcher(None, old, new).ratio()
