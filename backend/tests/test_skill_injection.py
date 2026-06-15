import litellm
from core.general_chat_orchestrator import GeneralChatOrchestrator
from core.llm.types import ResolvedCall

RC = ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"})


async def test_skills_block_injected_into_system(monkeypatch):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        class _D:
            content = "ok"
        class _C:
            def __init__(self): self.delta = _D(); self.message = _D()
        async def gen():
            yield type("Ch", (), {"choices": [_C()], "usage": None})()
        return gen()

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "cost_per_token", lambda **kw: (0.0, 0.0))

    orch = GeneralChatOrchestrator()
    await orch.process("hi", history=[], memories=[], resolved=RC, stream_cb=None, skills_block="SKILL-MARKER-123")
    system = captured["messages"][0]
    assert system["role"] == "system"
    assert "SKILL-MARKER-123" in system["content"]
