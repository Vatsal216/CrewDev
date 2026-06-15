import pytest
import litellm

from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall, LLMError


# ---- Fakes that look like LiteLLM's response objects -------------------

class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)        # streaming shape
        self.message = _Delta(content)      # non-streaming shape (also has .content)


class _Usage:
    def __init__(self, p, c):
        self.prompt_tokens = p
        self.completion_tokens = c


class _Chunk:
    def __init__(self, content=None, usage=None):
        self.choices = [_Choice(content)]
        self.usage = usage


class _Response:
    def __init__(self, content, usage):
        self.choices = [_Choice(content)]
        self.usage = usage


def _install_fakes(monkeypatch, *, raise_exc=None, cost_calls=None):
    async def fake_acompletion(**kwargs):
        if raise_exc is not None:
            raise raise_exc
        if kwargs.get("stream"):
            async def gen():
                yield _Chunk("Hello ")
                yield _Chunk("world")
                yield _Chunk(None, usage=_Usage(10, 5))
            return gen()
        return _Response("the answer", _Usage(7, 3))

    def fake_cost_per_token(**kw):
        if cost_calls is not None:
            cost_calls.append(kw)
        return (0.0014, 0.0007)  # sums to 0.0021

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    # acomplete (has a response object) prices via completion_cost;
    # astream (token counts only) prices via cost_per_token.
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0021)
    monkeypatch.setattr(litellm, "cost_per_token", fake_cost_per_token)


async def test_astream_emits_tokens_and_returns_usage(monkeypatch):
    cost_calls = []
    _install_fakes(monkeypatch, cost_calls=cost_calls)
    events = []

    async def emit(e):
        events.append(e)

    router = LLMRouter()
    text, usage = await router.astream(
        [{"role": "user", "content": "hi"}],
        ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}),
        emit=emit,
    )

    assert text == "Hello world"
    assert events == [
        {"type": "token", "text": "Hello "},
        {"type": "token", "text": "world"},
    ]
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5
    assert usage.cost_usd == 0.0021
    assert usage.model == "openai/gpt-4o"
    # Regression guard: streaming cost must be priced from token counts via
    # cost_per_token (completion_cost does NOT accept token-count kwargs).
    assert cost_calls and cost_calls[-1]["prompt_tokens"] == 10
    assert cost_calls[-1]["completion_tokens"] == 5


async def test_emit_callback_error_is_not_wrapped_as_llmerror(monkeypatch):
    _install_fakes(monkeypatch)

    class EmitBoom(Exception):
        pass

    async def bad_emit(e):
        raise EmitBoom("transport closed")

    router = LLMRouter()
    # An emit/transport failure must surface as itself, not as a normalized LLMError.
    with pytest.raises(EmitBoom):
        await router.astream(
            [{"role": "user", "content": "hi"}],
            ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}),
            emit=bad_emit,
        )


async def test_acomplete_returns_text_and_usage(monkeypatch):
    _install_fakes(monkeypatch)
    router = LLMRouter()
    text, usage = await router.acomplete(
        [{"role": "user", "content": "q"}],
        ResolvedCall(model="anthropic/claude-sonnet-4-6", kwargs={"api_key": "k"}),
    )
    assert text == "the answer"
    assert usage.input_tokens == 7
    assert usage.output_tokens == 3
    assert usage.cost_usd == 0.0021


async def test_auth_error_is_normalized(monkeypatch):
    class AuthenticationError(Exception):
        pass

    _install_fakes(monkeypatch, raise_exc=AuthenticationError("bad key"))
    router = LLMRouter()
    with pytest.raises(LLMError) as ei:
        await router.acomplete(
            [{"role": "user", "content": "q"}],
            ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "bad"}),
        )
    assert ei.value.code == "auth"


async def test_system_prompt_is_prepended(monkeypatch):
    captured = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Response("ok", _Usage(1, 1))

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)
    router = LLMRouter()
    await router.acomplete(
        [{"role": "user", "content": "q"}],
        ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}),
        system="be terse",
    )
    assert captured["messages"][0] == {"role": "system", "content": "be terse"}
    assert captured["api_key"] == "k"
