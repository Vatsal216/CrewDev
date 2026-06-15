import litellm
from core.general_chat_orchestrator import GeneralChatOrchestrator, auto_title, memory_candidate
from core.llm.types import ResolvedCall


class _Delta:
    def __init__(self, c): self.content = c


class _Choice:
    def __init__(self, c): self.delta = _Delta(c); self.message = _Delta(c)


class _Usage:
    def __init__(self, p, c): self.prompt_tokens = p; self.completion_tokens = c


class _Chunk:
    def __init__(self, c=None, u=None): self.choices = [_Choice(c)]; self.usage = u


def _install(monkeypatch):
    async def fake_acompletion(**kwargs):
        async def gen():
            yield _Chunk("Hi ")
            yield _Chunk("there")
            yield _Chunk(None, u=_Usage(12, 4))
        return gen()
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "cost_per_token", lambda **kw: (0.0, 0.0))


async def test_process_streams_and_returns(monkeypatch):
    _install(monkeypatch)
    events = []

    async def cb(e):
        events.append(e)

    orch = GeneralChatOrchestrator()
    out = await orch.process(
        "hello",
        history=[{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "ok"}],
        memories=["likes brevity"],
        resolved=ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}),
        stream_cb=cb,
    )
    assert out == "Hi there"
    assert {"type": "token", "text": "Hi "} in events
    assert any(e["type"] == "usage" for e in events)
    usage_evt = [e for e in events if e["type"] == "usage"][0]
    assert usage_evt["total_tokens"] == 16


def test_auto_title_and_memory_candidate_unchanged():
    assert auto_title("short question") == "short question"
    assert memory_candidate("remember that I use vim", "ok") is not None
    assert memory_candidate("what time is it", "noon") is None


async def test_web_disabled_does_not_search(monkeypatch):
    """Default (web off): the web-search seam must not be called."""
    _install(monkeypatch)
    import core.general_chat_orchestrator as gco

    called = {"n": 0}

    def spy(query, max_results=5):
        called["n"] += 1
        return "should not be used"

    monkeypatch.setattr(gco, "_web_search", spy)
    out = await GeneralChatOrchestrator().process(
        "hello",
        history=[],
        memories=[],
        resolved=ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}),
    )
    assert out == "Hi there"
    assert called["n"] == 0


async def test_web_enabled_injects_search_results(monkeypatch):
    """web_enabled=True grounds the prompt in search results and emits a web_search event."""
    captured = {}

    async def fake_acompletion(**kwargs):
        captured["messages"] = kwargs.get("messages")

        async def gen():
            yield _Chunk("answer")
            yield _Chunk(None, u=_Usage(5, 2))
        return gen()

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "cost_per_token", lambda **kw: (0.0, 0.0))

    import core.general_chat_orchestrator as gco
    monkeypatch.setattr(
        gco, "_web_search",
        lambda q, max_results=5: "SOURCE: https://x.test\nTITLE: X\nCONTENT: latest news about Y",
    )

    events = []

    async def cb(e):
        events.append(e)

    out = await GeneralChatOrchestrator().process(
        "what's new in Y",
        history=[],
        memories=[],
        resolved=ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}),
        stream_cb=cb,
        web_enabled=True,
    )
    assert out == "answer"
    blob = str(captured["messages"])
    assert "latest news about Y" in blob  # web context reached the model
    assert "https://x.test" in blob
    assert any(e.get("type") == "web_search" for e in events)


async def test_web_enabled_search_error_still_answers(monkeypatch):
    """If search fails (e.g. no Tavily key), the chat still answers — no crash."""
    _install(monkeypatch)
    import core.general_chat_orchestrator as gco
    monkeypatch.setattr(
        gco, "_web_search",
        lambda q, max_results=5: "ERROR: Web search failed: no api key",
    )

    events = []

    async def cb(e):
        events.append(e)

    out = await GeneralChatOrchestrator().process(
        "hi",
        history=[],
        memories=[],
        resolved=ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}),
        stream_cb=cb,
        web_enabled=True,
    )
    assert out == "Hi there"  # graceful fallback to a normal answer
    web_events = [e for e in events if e.get("type") == "web_search"]
    assert web_events and web_events[-1].get("ok") is False
