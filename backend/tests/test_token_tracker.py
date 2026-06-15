from core.token_tracker import TokenTracker
from core.llm.types import Usage


def test_add_accumulates_tokens_and_cost():
    t = TokenTracker()
    t.add(input_tokens=100, output_tokens=50, cost_usd=0.01, agent="planner", model="openai/gpt-4o")
    t.add(input_tokens=200, output_tokens=80, cost_usd=0.02, agent="synthesizer", model="openai/gpt-4o")
    s = t.summary()
    assert s["input_tokens"] == 300
    assert s["output_tokens"] == 130
    assert s["total_tokens"] == 430
    assert s["calls"] == 2
    assert s["cost_usd"] == 0.03
    assert s["by_agent"]["planner"]["in"] == 100
    assert s["by_agent"]["synthesizer"]["cost"] == 0.02


def test_add_usage_from_router_usage_object():
    t = TokenTracker()
    t.add_usage(Usage(input_tokens=10, output_tokens=5, cost_usd=0.001, model="ollama_chat/llama3"), agent="chat")
    s = t.summary()
    assert s["total_tokens"] == 15
    assert s["cost_usd"] == 0.001
    assert s["by_agent"]["chat"]["model"] == "ollama_chat/llama3"


def test_over_budget():
    t = TokenTracker()
    t.add(input_tokens=120_000, output_tokens=90_000, cost_usd=1.0)
    assert t.over_budget(200_000) is True
    assert t.over_budget(300_000) is False
