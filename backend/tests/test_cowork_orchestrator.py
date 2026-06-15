import litellm
from core.cowork_orchestrator import CoworkOrchestrator, parse_reply_and_doc
from core.llm.types import ResolvedCall

RC = ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"})


class _Msg:
    def __init__(self, c): self.content = c
class _Choice:
    def __init__(self, c): self.message = _Msg(c)
class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]; self.usage = None


def test_parse_reply_and_doc():
    reply, doc = parse_reply_and_doc("Sure!\n<doc>\n# Title\n</doc>")
    assert reply == "Sure!"
    assert doc == "# Title"
    reply2, doc2 = parse_reply_and_doc("Just chatting, no doc change.")
    assert reply2 == "Just chatting, no doc change."
    assert doc2 is None


async def test_process_emits_reply_and_doc_update(monkeypatch):
    async def fake_acompletion(**kw):
        return _Resp("Done.\n<doc>\n# README\nhi\n</doc>")
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)

    events = []
    async def cb(e): events.append(e)

    orch = CoworkOrchestrator()
    reply, new_doc = await orch.process("write a readme", history=[], doc_content="", resolved=RC, stream_cb=cb)
    assert reply == "Done."
    assert new_doc == "# README\nhi"
    assert any(e["type"] == "token" for e in events)
    assert any(e["type"] == "doc_update" and e["doc"] == "# README\nhi" for e in events)
