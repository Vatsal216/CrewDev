import litellm
from core.validator import OutputValidator
from core.llm.types import ResolvedCall


class _Msg:
    def __init__(self, c): self.content = c


class _Choice:
    def __init__(self, c): self.message = _Msg(c)


class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]; self.usage = None


async def test_evaluate_parses_verdict(monkeypatch):
    async def fake_acompletion(**kw):
        return _Resp('{"passed": true, "score": 0.9, "feedback": "Looks good"}')
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)

    v = OutputValidator()
    verdict = await v.evaluate("some output", "the task", resolved=ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}))
    assert verdict.passed is True
    assert verdict.score == 0.9


async def test_evaluate_parse_error_assumes_pass(monkeypatch):
    async def fake_acompletion(**kw):
        return _Resp("not json")
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)

    v = OutputValidator()
    verdict = await v.evaluate("x", "task", resolved=ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"}))
    assert verdict.passed is True
