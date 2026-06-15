from core.engines.registry import get_engine
from core.engines.base import ProjectEngine
from core.orchestrator import MainOrchestrator
from core.llm.types import ResolvedCall

RC = ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"})


def test_crewai_is_default_and_fallback():
    assert isinstance(get_engine("crewai", "p", "s", RC), MainOrchestrator)
    assert isinstance(get_engine(None, "p", "s", RC), MainOrchestrator)
    assert isinstance(get_engine("bogus", "p", "s", RC), MainOrchestrator)


def test_deepagents_engine_selected():
    eng = get_engine("deepagents", "p", "s", RC)
    assert eng.__class__.__name__ == "DeepAgentsEngine"
    assert hasattr(eng, "process")


def test_main_orchestrator_satisfies_interface():
    assert hasattr(ProjectEngine, "process")
