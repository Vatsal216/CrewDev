import os
from core.engines.deepagents_tools import build_tools
from config import settings


def test_build_tools_count():
    tools = build_tools("p_da")
    assert len(tools) == 8


async def test_file_write_then_read_roundtrip():
    os.makedirs(os.path.join(settings.workspace_path, "p_da"), exist_ok=True)
    tools = {t.name: t for t in build_tools("p_da")}
    w = await tools["write_file"].ainvoke({"path": "note.txt", "content": "hello-da"})
    assert "OK" in w
    r = await tools["read_file"].ainvoke({"path": "note.txt"})
    assert "hello-da" in r


async def test_bash_tool_rejects_injection():
    os.makedirs(os.path.join(settings.workspace_path, "p_da"), exist_ok=True)
    tools = {t.name: t for t in build_tools("p_da")}
    out = await tools["run_bash"].ainvoke({"command": "echo a && rm -rf ~"})
    assert "ERROR" in out
