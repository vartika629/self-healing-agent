"""Tests for the sandbox (executor.py)."""
from executor import check_safety, parse_error, run_script


def test_working_script_succeeds():
    r = run_script('print("hi")')
    assert r.success
    assert r.stdout.strip() == "hi"


def test_runtime_error_is_captured():
    r = run_script("x = 1 / 0")
    assert not r.success
    assert r.error_type == "ZeroDivisionError"
    assert "division by zero" in r.stderr


def test_syntax_error_is_captured():
    r = run_script("def f(:\n    pass")
    assert not r.success
    assert r.error_type == "SyntaxError"


def test_missing_module_detected():
    r = run_script("import maths")
    assert r.error_type == "ModuleNotFoundError"
    assert r.missing_module == "maths"


def test_infinite_loop_times_out():
    r = run_script("while True:\n    pass", timeout=1)
    assert r.timed_out
    assert not r.success
    assert "infinite loop" in r.error_text


def test_output_is_truncated():
    r = run_script('print("a" * 50000)', max_output=100)
    assert "output cut" in r.stdout
    assert len(r.stdout) < 200


def test_temp_path_hidden_from_traceback():
    r = run_script("raise ValueError('boom')")
    assert 'File "script.py"' in r.stderr


def test_dangerous_calls_are_blocked():
    assert check_safety("import os\nos.system('ls')")
    assert check_safety("import shutil\nshutil.rmtree('/')")
    assert check_safety("from shutil import rmtree\nrmtree('/')")
    assert check_safety("import os as o\no.remove('x')")
    assert check_safety("import requests")
    assert check_safety("import socket")
    assert check_safety("eval('1+1')")


def test_blocked_script_is_never_run():
    r = run_script("import os\nos.system('echo hacked')")
    assert not r.success
    assert r.blocked
    assert r.stdout == ""


def test_blocking_works_even_with_syntax_error():
    assert check_safety("import os\nos.system('ls'\nprint(")


def test_safe_code_has_no_warnings():
    assert check_safety("import math\nprint(math.sqrt(4))") == []


def test_parse_error():
    tb = 'Traceback...\n  File "script.py", line 1\nNameError: name \'x\' is not defined'
    assert parse_error(tb) == ("NameError", "name 'x' is not defined")
