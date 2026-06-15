from core.orchestrator import MainOrchestrator


def get_engine(name, project_id: str, session_id: str, resolved):
    if name == "deepagents":
        from core.engines.deepagents_engine import DeepAgentsEngine
        return DeepAgentsEngine(project_id, session_id, resolved)
    # default + fallback: CrewAI
    return MainOrchestrator(project_id, session_id, resolved)
