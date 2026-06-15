import pytest
from core.sandbox.runner import run_subprocess, run_python, safe_argv


def test_safe_argv_accepts_and_splits():
    assert safe_argv("python main.py", {"python"}) == ["python", "main.py"]


def test_safe_argv_rejects_metachars():
    with pytest.raises(ValueError):
        safe_argv("echo x && rm -rf ~", {"echo"})
    with pytest.raises(ValueError):
        safe_argv("ls | sh", {"ls"})


def test_safe_argv_rejects_non_allowlisted():
    with pytest.raises(ValueError):
        safe_argv("curl http://x", {"echo"})


def test_run_subprocess_captures_stdout(tmp_path):
    res = run_subprocess(["echo", "hello"], cwd=str(tmp_path))
    assert res.exit_code == 0
    assert "hello" in res.stdout
    assert res.timed_out is False


def test_run_subprocess_timeout(tmp_path):
    res = run_subprocess(["sleep", "5"], cwd=str(tmp_path), timeout=1)
    assert res.timed_out is True


def test_run_python_captures_and_collects_artifacts(tmp_path):
    code = "print(2 + 2)\nopen('out.txt','w').write('hi')\n"
    res, artifacts = run_python(code, str(tmp_path / "run1"))
    assert "4" in res.stdout
    assert "out.txt" in artifacts
