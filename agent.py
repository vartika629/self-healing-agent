"""
agent.py - The self-healing LOOP (the "agent" part).

The loop:
    1. RUN the script in the sandbox            (executor.run_script)
    2. If it works  -> STOP, success.
    3. If it fails  -> send code + error to the AI (llm.ask_llm_for_fix)
    4. APPLY the AI's fix and go back to step 1.

Guards that stop the loop from running forever:
    - max_fixes:        hard limit on number of AI fixes (default 5)
    - no-change check:  if the AI returns the same code, it is stuck -> stop
    - cycle check:      if the AI returns a version we already tried -> stop
    - safety check:     dangerous original code is never run or sent to the AI
    - timeout:          each run is killed after N seconds (infinite loops)
"""

from __future__ import annotations

import difflib
import hashlib
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from diff_utils import diff_stats, make_diff
from executor import DEFAULT_TIMEOUT, RunResult, run_script
from llm import Fix, LLMError, ask_llm_for_fix

# A "fixer" is any function: (code, error_text, history) -> Fix
# The real one calls the LLM; tests pass in a fake one.
Fixer = Callable[[str, str, list], Fix]


@dataclass
class Attempt:
    number: int                       # 1 = the original script
    code: str
    result: RunResult
    explanation: str | None = None    # what the AI changed to make THIS version
    diff: str = ""                    # diff from the previous version
    lines_added: int = 0
    lines_removed: int = 0
    seconds: float = 0.0


@dataclass
class HealResult:
    success: bool
    attempts: list[Attempt]
    final_code: str
    stop_reason: str                  # human-readable reason the loop ended
    import_hints: list[str] = field(default_factory=list)
    total_seconds: float = 0.0

    @property
    def fixes_used(self) -> int:
        return max(0, len(self.attempts) - 1)


def _fingerprint(code: str) -> str:
    """Hash of the code ignoring trailing spaces / blank lines (for cycle checks)."""
    norm = "\n".join(line.rstrip() for line in code.strip().splitlines())
    return hashlib.sha256(norm.encode()).hexdigest()


def import_hint(module: str) -> str:
    """Explain a missing module: typo of a standard module, or needs pip install."""
    stdlib = getattr(sys, "stdlib_module_names", set())
    close = difflib.get_close_matches(module, stdlib, n=1, cutoff=0.75)
    if close and close[0] != module:
        return f"`{module}` not found. Did you mean the built-in module `{close[0]}`?"
    return (
        f"`{module}` is not installed. Install it yourself with: "
        f"`pip install {module}` (the agent never installs packages automatically)."
    )


def heal(
    code: str,
    fixer: Fixer = ask_llm_for_fix,
    max_fixes: int = 5,
    timeout: int = DEFAULT_TIMEOUT,
    on_attempt: Callable[[Attempt], None] | None = None,
) -> HealResult:
    """Run the self-healing loop and return everything that happened."""
    start = time.time()
    attempts: list[Attempt] = []
    seen = {_fingerprint(code)}
    history: list[str] = []
    hints: list[str] = []
    explanation: str | None = None
    previous: str | None = None

    def finish(success: bool, reason: str) -> HealResult:
        return HealResult(
            success=success,
            attempts=attempts,
            final_code=code,
            stop_reason=reason,
            import_hints=hints,
            total_seconds=round(time.time() - start, 2),
        )

    for i in range(max_fixes + 1):
        # ---- 1. RUN ------------------------------------------------------
        t0 = time.time()
        result = run_script(code, timeout=timeout)
        added, removed = diff_stats(previous, code) if previous is not None else (0, 0)
        attempt = Attempt(
            number=i + 1,
            code=code,
            result=result,
            explanation=explanation,
            diff=make_diff(previous, code, f"v{i}", f"v{i + 1}") if previous is not None else "",
            lines_added=added,
            lines_removed=removed,
            seconds=round(time.time() - t0, 2),
        )
        attempts.append(attempt)
        if on_attempt:
            on_attempt(attempt)

        # ---- 2. SUCCESS? -------------------------------------------------
        if result.success:
            if i == 0:
                return finish(True, "The script already works - nothing to fix.")
            return finish(True, f"Fixed after {i} AI fix(es).")

        if result.missing_module:
            hint = import_hint(result.missing_module)
            if hint not in hints:
                hints.append(hint)

        if result.blocked and i == 0:
            return finish(False, "Stopped: the script contains blocked (dangerous) code, "
                                 "so it was not run.")

        if i == max_fixes:
            return finish(False, f"Stopped: reached the limit of {max_fixes} AI fixes.")

        # ---- 3. ASK THE AI FOR A FIX -------------------------------------
        try:
            fix = fixer(code, result.error_text, history)
        except LLMError as exc:
            return finish(False, f"Stopped: AI error - {exc}")

        # ---- 4. LOOP GUARDS ----------------------------------------------
        fp = _fingerprint(fix.code)
        if fp == _fingerprint(code):
            return finish(False, "Stopped: the AI returned the same code (it is stuck).")
        if fp in seen:
            return finish(False, "Stopped: the AI went back to a version it already "
                                 "tried (a loop was detected).")
        seen.add(fp)

        # ---- 5. APPLY THE FIX and go round again -------------------------
        history.append(f"Attempt {i + 1}: {fix.explanation}")
        previous, code, explanation = code, fix.code, fix.explanation

    return finish(False, "Stopped.")  # not reached, keeps type-checkers happy
