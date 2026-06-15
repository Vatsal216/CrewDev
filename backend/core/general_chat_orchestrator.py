from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from core.attachments import build_user_content
from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall
from core.token_tracker import TokenTracker

StreamCallback = Callable[[dict], Awaitable[None]]


def _web_search(query: str, max_results: int = 5) -> str:
    """Module-level seam — run the CrewAI WebSearchTool (Tavily-backed).

    Imported lazily so general chat stays free of the heavy crewai/tools stack
    whenever web search is OFF. Returns formatted results, or an ``ERROR: …``
    string on failure (e.g. missing TAVILY_API_KEY). Patched in tests.
    """
    from tools.all_tools import WebSearchTool

    return WebSearchTool()._run(query, max_results=max_results)


class GeneralChatOrchestrator:
    """Claude-style general chat, now provider-agnostic via LLMRouter.

    Intentionally separate from MainOrchestrator: no project creation, no project
    file access, no bash/code tools, no project harness mutation. DB-free — the
    caller resolves the provider selection and passes a ResolvedCall.
    """

    def __init__(self):
        self.router = LLMRouter()

    async def process(
        self,
        user_message: str,
        history: list[dict],
        memories: list[str],
        resolved: ResolvedCall,
        stream_cb: Optional[StreamCallback] = None,
        skills_block: str = "",
        attachments_text: str = "",
        attachment_images=None,
        web_enabled: bool = False,
    ) -> str:
        tracker = TokenTracker()

        async def emit(event: dict):
            if stream_cb:
                await stream_cb(event)

        memory_block = "\n".join(f"- {m}" for m in memories[:20]) if memories else "No saved chat memory yet."

        system = f"""You are CrewDev Chat, a Claude-style general assistant inside an agentic developer platform.

Rules:
- This is GENERAL CHAT, not project mode.
- Do not create projects from chat.
- Do not claim you can read project files unless the user is in Projects mode.
- Use the saved user memory only when relevant.
- Be direct, practical, and concise.

Saved chat memory:
{memory_block}
"""
        if skills_block:
            system = f"{skills_block}\n\n{system}"

        if web_enabled:
            web_block = await self._gather_web(user_message, emit)
            if web_block:
                system = f"{system}\n{web_block}"

        messages = []
        for m in history[-30:]:
            role = m.get("role")
            content = m.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": build_user_content(user_message, attachments_text, attachment_images)})

        text, usage = await self.router.astream(
            messages, resolved, system=system, max_tokens=4000, emit=emit
        )
        tracker.add_usage(usage, agent="chat")
        await emit({"type": "usage", **tracker.summary()})
        return text.strip()

    async def _gather_web(self, query: str, emit: StreamCallback) -> str:
        """Run a live web search and return a system-prompt grounding block.

        Emits a ``web_search`` event when it starts and another with ``ok`` when
        it finishes. Never raises: on any failure (missing key, network) it
        returns "" so the chat answers normally.
        """
        await emit({"type": "web_search", "query": query[:200]})
        try:
            raw = await asyncio.to_thread(_web_search, query)
        except Exception as e:  # noqa: BLE001 — fail open, web is best-effort
            raw = f"ERROR: Web search failed: {e}"

        ok = bool(raw.strip()) and not raw.lstrip().startswith("ERROR:")
        await emit({"type": "web_search", "ok": ok, "query": query[:200]})
        if not ok:
            return ""
        return (
            "Live web search results for the user's request — use these to ground "
            "your answer and cite sources by URL when you rely on them:\n\n"
            f"{raw.strip()}\n"
        )


def auto_title(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return "New chat"
    if len(cleaned) <= 44:
        return cleaned
    return cleaned[:44].rstrip() + "…"


def memory_candidate(user_message: str, assistant_message: str) -> str | None:
    """Lightweight heuristic memory extraction — only explicit preference/identity
    statements worth remembering for future chats."""
    text = user_message.strip()
    lowered = text.lower()
    triggers = [
        "remember that", "from now on", "going forward",
        "i prefer", "my preference", "i want you to", "call me",
    ]
    if any(t in lowered for t in triggers):
        return text[:600]
    return None
