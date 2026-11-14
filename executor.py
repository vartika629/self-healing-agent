"""
executor.py - The "sandbox".

Runs a Python script safely and reports what happened.

Safety layers:
  1. Static check (before running): scan the code with Python's `ast` module and
     block obviously dangerous things (deleting files, shell commands, network).
  2. Separate process: the script runs in its own subprocess, so if it crashes,
     our app does not crash.
  3. Temp folder: the script runs inside a fresh temporary directory that is
     deleted afterwards.
  4. Timeout: the script is killed after N seconds (catches infinite loops).
  5. Output limit: very long output is cut, so the UI does not freeze.

Note: this is a "best effort" sandbox for a college demo, NOT a real security
boundary. A determined attacker could get around a static check. See README
"Limitations".
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT = 10          # seconds
DEFAULT_MAX_OUTPUT = 10_000   # characters

# Function calls we refuse to run, written as "module.function".
BLOCKED_CALLS = {
    "os.system": "runs shell commands",
    "os.popen": "runs shell commands",
    "os.remove": "deletes files",
    "os.unlink": "deletes files",
    "os.rmdir": "deletes folders",
    "os.removedirs": "deletes folders",
    "os.kill": "kills processes",
    "os.fork": "creates processes",
    "shutil.rmtree": "deletes whole folders",
    "shutil.move": "moves files",
    "subprocess.run": "runs other programs",
    "subprocess.call": "runs other programs",
    "subprocess.Popen": "runs other programs",
    "subprocess.check_output": "runs other programs",
    "subprocess.check_call": "runs other programs",
}

# Modules whose import we refuse (mostly network access).
BLOCKED_MODULES = {
    "socket": "network access",
    "requests": "network access",
    "urllib": "network access",
    "http": "network access",
    "ftplib": "network access",
    "smtplib": "sending emails",
    "telnetlib": "network access",
    "ctypes": "low-level memory access",
}

# Built-in functions we refuse.
BLOCKED_BUILTINS = {
    "eval": "runs hidden code",
    "exec": "runs hidden code",
    "__import__": "hidden imports",
}


@dataclass
class RunResult:
    """Everything we learned from one run of the script."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    timed_out: bool = False
    error_type: str | None = None        # e.g. "ZeroDivisionError"
    error_message: str | None = None     # e.g. "division by zero"
    missing_module: str | None = None    # e.g. "numpy" (for pip install hint)
    blocked: list[str] = field(default_factory=list)  # safety warnings

    @property
    def error_text(self) -> str:
        """The text we show the LLM / user to explain the failure."""
        if self.blocked:
            return "BLOCKED for safety:\n" + "\n".join(self.blocked)
        if self.timed_out:
            return (
                f"TimeoutError: the script ran longer than the time limit and was "
                f"stopped. This usually means an infinite loop.\n{self.stderr}"
            ).strip()
        return self.stderr.strip()


# ---------------------------------------------------------------------------
# 1. Static safety check
# ---------------------------------------------------------------------------

def _dotted_name(node: ast.AST) -> str | None:
    """Turn an AST node like `os.path.join` into the string 'os.path.join'."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def check_safety(code: str) -> list[str]:
    """Return a list of human-readable warnings. Empty list = looks safe."""
    warnings: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Code cannot be parsed (it has a syntax error). Fall back to a simple
        # text search so we still catch the obvious stuff.
        for name, why in {**BLOCKED_CALLS, **BLOCKED_BUILTINS}.items():
            if re.search(rf"\b{re.escape(name)}\s*\(", code):
                warnings.append(f"`{name}` is not allowed ({why}).")
        for mod, why in BLOCKED_MODULES.items():
            if re.search(rf"^\s*(import|from)\s+{mod}\b", code, re.MULTILINE):
                warnings.append(f"Importing `{mod}` is not allowed ({why}).")
        return warnings

    # Remember aliases like `import os as o` or `from shutil import rmtree`.
    aliases: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    warnings.append(
                        f"Importing `{a.name}` is not allowed ({BLOCKED_MODULES[root]})."
                    )
                aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in BLOCKED_MODULES:
                warnings.append(
                    f"Importing from `{node.module}` is not allowed ({BLOCKED_MODULES[root]})."
                )
            for a in node.names:
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted_name(node.func)
        if not name:
            continue
        # Resolve alias: `o.system` -> `os.system`, `rmtree` -> `shutil.rmtree`
        first, _, rest = name.partition(".")
        full = aliases.get(first, first) + (f".{rest}" if rest else "")
        if full in BLOCKED_CALLS:
            warnings.append(f"`{full}()` is not allowed ({BLOCKED_CALLS[full]}).")
        elif name in BLOCKED_BUILTINS:
            warnings.append(f"`{name}()` is not allowed ({BLOCKED_BUILTINS[name]}).")

    # Remove duplicates but keep order.
    return list(dict.fromkeys(warnings))


# ---------------------------------------------------------------------------
# 2. Error parsing helpers
# ---------------------------------------------------------------------------

_ERROR_LINE = re.compile(r"^(\w+(?:\.\w+)*(?:Error|Exception|Exit|Interrupt)):?\s*(.*)$")
_MISSING_MODULE = re.compile(r"No module named '([\w\.]+)'")


def parse_error(stderr: str) -> tuple[str | None, str | None]:
    """Find the exception name and message in a traceback (last matching line)."""
    for line in reversed(stderr.strip().splitlines()):
        m = _ERROR_LINE.match(line.strip())
        if m:
            return m.group(1).split(".")[-1], m.group(2) or None
    return None, None


def find_missing_module(stderr: str) -> str | None:
    m = _MISSING_MODULE.search(stderr)
    return m.group(1).split(".")[0] if m else None


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [output cut: more than {limit} characters]"


# ---------------------------------------------------------------------------
# 3. Run the script
# ---------------------------------------------------------------------------

def run_script(
    code: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_output: int = DEFAULT_MAX_OUTPUT,
) -> RunResult:
    """Run `code` in a separate Python process and return a RunResult."""
    warnings = check_safety(code)
    if warnings:
        return RunResult(success=False, blocked=warnings, error_type="BlockedForSafety")

    with tempfile.TemporaryDirectory(prefix="selfheal_") as tmp:
        script = Path(tmp) / "script.py"
        script.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                # -I = isolated mode: ignores environment variables and the
                # user's site-packages folder for extra isolation.
                [sys.executable, "-I", str(script)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            return RunResult(
                success=False,
                stdout=_truncate(out, max_output),
                timed_out=True,
                error_type="TimeoutError",
                error_message=f"Script took longer than {timeout} seconds",
            )

    stdout = _truncate(proc.stdout, max_output)
    # Hide the temp folder path from tracebacks so the LLM sees a clean name.
    stderr = _truncate(proc.stderr.replace(str(script), "script.py"), max_output)
    success = proc.returncode == 0
    error_type, error_message = (None, None) if success else parse_error(stderr)

    return RunResult(
        success=success,
        stdout=stdout,
        stderr=stderr,
        returncode=proc.returncode,
        error_type=error_type,
        error_message=error_message,
        missing_module=None if success else find_missing_module(stderr),
    )
