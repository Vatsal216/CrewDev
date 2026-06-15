import core.engines.deepagents_engine as dae
from core.engines.deepagents_engine import DeepAgentsEngine
from core.llm.types import ResolvedCall

RC = ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"})


class _FakeMsg:
    def __init__(self, c): self.content = c


class _FakeAgent:
    async def ainvoke(self, payload):
        return {"messages": [_FakeMsg("DeepAgents reply here")]}


def test_construct():
    eng = DeepAgentsEngine("p", "s", RC)
    assert eng.resolved is RC


async def test_process_streams_and_returns(monkeypatch):
    # avoid importing real deepagents/model
    monkeypatch.setattr(dae, "_build_model", lambda resolved: object())
    monkeypatch.setattr(dae, "_build_agent", lambda model, tools, system: _FakeAgent())
    # harness.get_context touches the DB; stub it
    eng = DeepAgentsEngine("p", "s", RC)
    async def fake_ctx(): return "CONTEXT"
    monkeypatch.setattr(eng.harness, "get_context", fake_ctx)

    events = []
    async def cb(e): events.append(e)
    out = await eng.process("do it", stream_cb=cb, skills_block="SKILL")
    assert out == "DeepAgents reply here"
    assert any(e["type"] == "token" for e in events)
    assert any(e["type"] == "usage" for e in events)
