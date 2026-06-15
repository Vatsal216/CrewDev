import asyncio
from typing import Optional

from core.harness import ProjectHarness
from core.attachments import build_user_content
from core.engines.deepagents_tools import build_tools


def _build_model(resolved):
    from langchain_litellm import ChatLiteLLM
    return ChatLiteLLM(model=resolved.model, **resolved.kwargs)


def _build_agent(model, tools, system: str):
    from deepagents import create_deep_agent
    return create_deep_agent(model=model, tools=tools, system_prompt=system)


def _final_text(result) -> str:
    msgs = result.get("messages", []) if isinstance(result, dict) else []
    for m in reversed(msgs):
        c = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        if c:
            return c if isinstance(c, str) else str(c)
    return ""


class DeepAgentsEngine:
    """Project engine backed by DeepAgents (LangGraph), running through our provider
    routing (ChatLiteLLM) with the project tools re-wrapped from the CrewAI tools."""

    def __init__(self, project_id: str, session_id: str, resolved):
        self.project_id = project_id
        self.session_id = session_id
        self.resolved = resolved
        self.harness = ProjectHarness(project_id)

    async def process(self, user_message: str, stream_cb=None, *, skills_block: str = "",
                      attachments_text: str = "", attachment_images: Optional[list] = None) -> str:
        async def emit(event: dict):
            if stream_cb:
                await stream_cb(event)

        await emit({"type": "status", "message": "DeepAgents: working…"})
        try:
            context = await self.harness.get_context()
            system = f"{skills_block}\n\n{context}" if skills_block else context
            model = _build_model(self.resolved)
            agent = _build_agent(model, build_tools(self.project_id), system)
            content = build_user_content(user_message, attachments_text, attachment_images)
            result = await agent.ainvoke({"messages": [{"role": "user", "content": content}]})
            final = _final_text(result)
        except Exception as e:
            final = f"DeepAgents error: {e}"
            await emit({"type": "error", "message": str(e)})

        for i in range(0, len(final), 24):
            await emit({"type": "token", "text": final[i:i + 24]})
            await asyncio.sleep(0.005)
        await emit({"type": "usage", "input_tokens": 0, "output_tokens": 0,
                    "total_tokens": 0, "cost_usd": 0.0, "calls": 1, "by_agent": {}})
        return final
