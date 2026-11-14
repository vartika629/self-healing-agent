"""Tests for the self-healing loop (agent.py), using a FAKE AI so no API key is needed."""
from agent import heal, import_hint
from llm import Fix, LLMError, parse_response

BROKEN = 'print(1 / 0)\n'
FIXED = 'print(1 / 1)\n'


def fixer_returning(*codes):
    """Fake AI that returns the given code versions one by one."""
    calls = []

    def fixer(code, error, history):
        calls.append((code, error, list(history)))
        return Fix(code=codes[len(calls) - 1], explanation=f"fix {len(calls)}")

    fixer.calls = calls
    return fixer


def test_already_working_script_needs_no_fix():
    fixer = fixer_returning()
    res = heal('print("ok")\n', fixer=fixer)
    assert res.success and res.fixes_used == 0
    assert fixer.calls == []


def test_fixed_in_one_attempt():
    fixer = fixer_returning(FIXED)
    res = heal(BROKEN, fixer=fixer)
    assert res.success
    assert res.fixes_used == 1
    assert res.final_code == FIXED
    assert "ZeroDivisionError" in fixer.calls[0][1]   # AI received the error
    assert "+print(1 / 1)" in res.attempts[1].diff     # diff recorded


def test_fixed_after_several_attempts_and_history_is_passed():
    fixer = fixer_returning("print(2 / 0)\n", "print(3 / 0)\n", FIXED)
    res = heal(BROKEN, fixer=fixer)
    assert res.success and res.fixes_used == 3
    assert len(fixer.calls[2][2]) == 2                 # 2 earlier fixes in history


def test_stops_at_max_attempts():
    bad_versions = [f"print({i} / 0)\n" for i in range(2, 10)]
    res = heal(BROKEN, fixer=fixer_returning(*bad_versions), max_fixes=3)
    assert not res.success
    assert res.fixes_used == 3
    assert "limit" in res.stop_reason


def test_stops_when_ai_returns_same_code():
    res = heal(BROKEN, fixer=fixer_returning(BROKEN))
    assert not res.success
    assert "same code" in res.stop_reason


def test_detects_cycle_back_to_old_version():
    res = heal(BROKEN, fixer=fixer_returning("print(2 / 0)\n", BROKEN))
    assert not res.success
    assert "loop was detected" in res.stop_reason


def test_dangerous_script_not_sent_to_ai():
    fixer = fixer_returning()
    res = heal("import os\nos.system('ls')\n", fixer=fixer)
    assert not res.success
    assert fixer.calls == []
    assert "blocked" in res.stop_reason


def test_dangerous_fix_from_ai_is_blocked_then_retried():
    fixer = fixer_returning("import os\nos.system('ls')\n", FIXED)
    res = heal(BROKEN, fixer=fixer)
    assert res.success
    assert res.attempts[1].result.blocked


def test_ai_error_stops_loop_gracefully():
    def broken_ai(code, error, history):
        raise LLMError("no internet")
    res = heal(BROKEN, fixer=broken_ai)
    assert not res.success
    assert "no internet" in res.stop_reason


def test_on_attempt_callback_called_live():
    seen = []
    heal(BROKEN, fixer=fixer_returning(FIXED), on_attempt=seen.append)
    assert [a.number for a in seen] == [1, 2]


def test_import_hints():
    assert "math" in import_hint("maths")
    assert "pip install numpy" in import_hint("numpy")


def test_parse_llm_response():
    text = "EXPLANATION: Fixed the typo.\n```python\nprint('hi')\n```"
    fix = parse_response(text)
    assert fix.explanation == "Fixed the typo."
    assert fix.code == "print('hi')\n"
