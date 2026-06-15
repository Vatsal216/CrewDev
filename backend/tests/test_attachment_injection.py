import litellm
from core.general_chat_orchestrator import GeneralChatOrchestrator
from core.llm.types import ResolvedCall

RC = ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"})


async def test_attachments_build_multimodal_user_message(monkeypatch):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        class _D: content = "ok"
        class _C:
            def __init__(self): self.delta = _D(); self.message = _D()
        async def gen():
            yield type("Ch", (), {"choices": [_C()], "usage": None})()
        return gen()

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "cost_per_token", lambda **kw: (0.0, 0.0))

    orch = GeneralChatOrchestrator()
    await orch.process("describe", history=[], memories=[], resolved=RC, stream_cb=None,
                       attachments_text="DOCTEXT", attachment_images=["data:image/png;base64,AAA"])
    user_msg = captured["messages"][-1]
    assert user_msg["role"] == "user"
    content = user_msg["content"]
    assert isinstance(content, list)
    assert any(b["type"] == "text" and "DOCTEXT" in b["text"] for b in content)
    assert any(b["type"] == "image_url" and b["image_url"]["url"] == "data:image/png;base64,AAA" for b in content)
