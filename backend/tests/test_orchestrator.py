import json
import litellm
from core.orchestrator import MainOrchestrator
from core.llm.types import ResolvedCall

RC = ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"})


class _Msg:
    def __init__(self, c): self.content = c


class _Choice:
    def __init__(self, c): self.message = _Msg(c); self.delta = _Msg(c)


class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]; self.usage = None


def test_init_is_lazy_no_memory_clients():
    orch = MainOrchestrator("proj", "sess", RC)
    assert orch._short_mem is None
    assert orch._long_mem is None
    assert orch.resolved is RC


async def test_plan_parses_json(monkeypatch):
    async def fake_acompletion(**kw):
        return _Resp(json.dumps({
            "reasoning": "simple",
            "subtasks": [{"id": "t1", "description": "do it", "agent_type": "analyst",
                          "expected_output": "answer", "success_criteria": "", "depends_on": []}],
        }))
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)

    from core.token_tracker import TokenTracker
    orch = MainOrchestrator("proj", "sess", RC)
    plan = await orch._plan("a question", context="", history="", memory="", tracker=TokenTracker())
    assert len(plan.subtasks) == 1
    assert plan.subtasks[0].agent_type == "analyst"


async def test_synthesize_single_result_streams_without_llm(monkeypatch):
    from core.token_tracker import TokenTracker
    orch = MainOrchestrator("proj", "sess", RC)
    events = []

    async def emit(e):
        events.append(e)

    out = await orch._synthesize_streaming("q", {"t1": "the only answer"}, "", "", emit, TokenTracker())
    assert out == "the only answer"
    assert any(e["type"] == "token" for e in events)
