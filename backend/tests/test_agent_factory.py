import pytest
from core.agent_factory import AgentFactory
from core.llm.types import ResolvedCall


def test_create_builds_agent_with_resolved_llm():
    f = AgentFactory("proj-test")
    agent = f.create("coder", ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "sk-k"}))
    assert agent.llm is not None
    assert "gpt-4o" in str(agent.llm.model)


@pytest.mark.parametrize("model,kwargs", [
    ("anthropic/claude-sonnet-4-6", {"api_key": "k"}),
    ("azure/mydeploy", {"api_key": "k", "api_base": "https://x.openai.azure.com", "api_version": "2024-06-01"}),
    ("ollama_chat/llama3", {"api_base": "http://localhost:11434"}),
])
def test_create_builds_agent_for_each_provider(model, kwargs):
    # Regression guard: crewai 1.14 needs crewai[anthropic] + crewai[azure-ai-inference]
    # extras installed, or LLM(model="anthropic/…"/"azure/…") raises at construction.
    f = AgentFactory("p")
    agent = f.create("analyst", ResolvedCall(model=model, kwargs=kwargs))
    assert agent.llm is not None


def test_infer_agent_type_unchanged():
    f = AgentFactory("p")
    assert f.infer_agent_type("write a pytest suite") == "tester"
    assert f.infer_agent_type("refactor this module") == "coder"
