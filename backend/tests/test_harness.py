import litellm
from core.harness import ProjectHarness
from core.llm.types import ResolvedCall


class _Msg:
    def __init__(self, c): self.content = c


class _Choice:
    def __init__(self, c): self.message = _Msg(c)


class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]; self.usage = None


async def test_update_merges_via_router(monkeypatch):
    async def fake_acompletion(**kw):
        return _Resp('{"goals": ["ship v1"], "summary": "A web app."}')
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)

    h = ProjectHarness("proj-x")
    h._state = {"goals": [], "architecture": "", "decisions": [], "active_tasks": [], "tech_stack": {}, "summary": ""}

    saved = {}
    async def fake_save():
        saved.update(h._state)
    monkeypatch.setattr(h, "_save", fake_save)

    await h.update("assistant said stuff", resolved=ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}))
    assert "ship v1" in saved["goals"]
    assert saved["summary"] == "A web app."
