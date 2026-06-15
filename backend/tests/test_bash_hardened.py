import os
from tools.all_tools import BashTool
from config import settings


def _workspace(pid):
    d = os.path.join(settings.workspace_path, pid)
    os.makedirs(d, exist_ok=True)
    return d


def test_bash_runs_allowed_command():
    _workspace("p_bash")
    out = BashTool(project_id="p_bash")._run("echo hi")
    assert "EXIT 0" in out
    assert "hi" in out


def test_bash_rejects_injection():
    _workspace("p_bash")
    out = BashTool(project_id="p_bash")._run("echo a && echo b")
    assert "ERROR" in out
    assert "EXIT" not in out


def test_bash_rejects_non_allowlisted():
    _workspace("p_bash")
    out = BashTool(project_id="p_bash")._run("rm -rf /")
    assert "ERROR" in out
