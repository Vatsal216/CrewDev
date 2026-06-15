from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse

from core.attachments import build_user_content
from core.general_chat_orchestrator import _web_search
from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall
from core.token_tracker import TokenTracker

StreamCallback = Callable[[dict], Awaitable[None]]


def _json_object_from_text(text: str) -> dict:
    """Best-effort JSON extraction for planner responses.

    We intentionally do not require provider-native JSON mode because some local
    and third-party providers may not support it. The planner is asked for JSON,
    and this helper tolerates markdown wrappers or surrounding text.
    """
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S | re.I)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start:end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _fetch_page(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"}:
        return "ERROR: Only http and https URLs can be fetched."
    from tools.all_tools import PageFetchTool

    return PageFetchTool()._run(url)


class GeneralAgentOrchestrator:
    """Tool-capable agent mode for normal General Chat.

    This stays deliberately separate from project agents. It can plan, perform
    web/research tool calls when web is enabled, and synthesize an answer, but it
    cannot read/write project files, run bash, mutate git, or create projects.
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
        trimmed_history = self._history_messages(history)
        user_content = build_user_content(user_message, attachments_text, attachment_images)

        await emit({"type": "agent_status", "message": "Agent mode enabled — planning task."})
        plan, plan_usage = await self._plan(
            user_message=user_message,
            user_content=user_content,
            history=trimmed_history,
            memory_block=memory_block,
            resolved=resolved,
            skills_block=skills_block,
            web_enabled=web_enabled,
        )
        tracker.add_usage(plan_usage, agent="general_agent_planner")

        await emit({
            "type": "agent_plan",
            "steps": plan.get("steps") or [],
            "tools": plan.get("tool_requests") or [],
            "mode": "agent",
        })

        tool_results = await self._run_tools(plan, web_enabled=web_enabled, emit=emit)

        system = self._final_system(
            memory_block=memory_block,
            skills_block=skills_block,
            web_enabled=web_enabled,
            plan=plan,
            tool_results=tool_results,
        )

        messages = trimmed_history + [{"role": "user", "content": user_content}]
        text, answer_usage = await self.router.astream(
            messages,
            resolved,
            system=system,
            max_tokens=5000,
            temperature=0.5,
            emit=emit,
        )
        tracker.add_usage(answer_usage, agent="general_agent_answer")
        await emit({"type": "usage", **tracker.summary()})
        await emit({"type": "agent_status", "message": "Agent task complete."})
        return text.strip()

    def _history_messages(self, history: list[dict]) -> list[dict]:
        messages = []
        for m in history[-30:]:
            role = m.get("role")
            content = m.get("content", "")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        return messages

    async def _plan(
        self,
        *,
        user_message: str,
        user_content,
        history: list[dict],
        memory_block: str,
        resolved: ResolvedCall,
        skills_block: str,
        web_enabled: bool,
    ):
        tools_text = (
            "Available tools: web_search(query, max_results), fetch_page(url)."
            if web_enabled else
            "No external tools are currently enabled. Web tools are disabled for this chat."
        )
        system = f"""You are the planner for CrewDev General Chat Agent Mode.

This is normal chat agent mode, not project mode.
Rules:
- Do not create projects.
- Do not claim access to project files, shell, git, or private workspace files.
- Use tools only when they materially improve the answer.
- Prefer a compact plan with 2-5 steps.
- Return ONLY valid JSON. No markdown.

{tools_text}

Saved chat memory:
{memory_block}
"""
        if skills_block:
            system = f"{skills_block}\n\n{system}"

        planner_prompt = f"""Plan the response for this user request.

User request:
{user_message}

Return JSON with this exact shape:
{{
  "task_type": "simple|research|analysis|coding|planning|troubleshooting",
  "needs_tools": true,
  "steps": ["step 1", "step 2"],
  "tool_requests": [
    {{"tool": "web_search", "query": "search query", "max_results": 5}},
    {{"tool": "fetch_page", "url": "https://example.com"}}
  ],
  "answer_style": "brief|normal|detailed"
}}

If web tools are disabled, set tool_requests to [] even if current data would help.
"""
        messages = history[-8:] + [{"role": "user", "content": planner_prompt}]
        raw, usage = await self.router.acomplete(
            messages,
            resolved,
            system=system,
            max_tokens=700,
        )
        plan = _json_object_from_text(raw)
        if not plan:
            plan = {
                "task_type": "analysis",
                "needs_tools": False,
                "steps": ["Understand the request", "Reason through the answer", "Provide a practical response"],
                "tool_requests": [],
                "answer_style": "normal",
            }
        plan["tool_requests"] = self._clean_tool_requests(plan.get("tool_requests") or [])
        if not web_enabled:
            plan["tool_requests"] = []
            plan["needs_tools"] = False
        return plan, usage

    def _clean_tool_requests(self, requests) -> list[dict]:
        cleaned = []
        if not isinstance(requests, list):
            return cleaned
        for req in requests[:4]:
            if not isinstance(req, dict):
                continue
            tool = str(req.get("tool") or "").strip()
            if tool == "web_search":
                query = str(req.get("query") or "").strip()
                if query:
                    max_results = req.get("max_results", 5)
                    try:
                        max_results = max(1, min(int(max_results), 8))
                    except Exception:
                        max_results = 5
                    cleaned.append({"tool": "web_search", "query": query[:300], "max_results": max_results})
            elif tool == "fetch_page":
                url = str(req.get("url") or "").strip()
                parsed = urlparse(url)
                if parsed.scheme in {"http", "https"}:
                    cleaned.append({"tool": "fetch_page", "url": url[:1000]})
        return cleaned

    async def _run_tools(self, plan: dict, *, web_enabled: bool, emit: StreamCallback) -> list[dict]:
        requests = plan.get("tool_requests") or []
        if not requests:
            return []
        if not web_enabled:
            await emit({"type": "agent_status", "message": "Tool use skipped because Web is off."})
            return []

        results = []
        for idx, req in enumerate(requests[:4], start=1):
            tool = req.get("tool")
            label = req.get("query") or req.get("url") or ""
            await emit({"type": "tool_call", "tool": tool, "input": label, "index": idx})
            try:
                if tool == "web_search":
                    raw = await asyncio.to_thread(_web_search, req["query"], req.get("max_results", 5))
                elif tool == "fetch_page":
                    raw = await asyncio.to_thread(_fetch_page, req["url"])
                else:
                    raw = f"ERROR: Unsupported tool: {tool}"
            except Exception as e:  # noqa: BLE001 — tool failures should not kill chat
                raw = f"ERROR: {tool} failed: {e}"

            ok = bool(raw.strip()) and not raw.lstrip().startswith("ERROR:")
            trimmed = raw.strip()
            if len(trimmed) > 7000:
                trimmed = trimmed[:7000] + "\n... [TRUNCATED]"
            results.append({"tool": tool, "input": label, "ok": ok, "output": trimmed})
            await emit({"type": "tool_result", "tool": tool, "ok": ok, "index": idx})
        return results

    def _final_system(
        self,
        *,
        memory_block: str,
        skills_block: str,
        web_enabled: bool,
        plan: dict,
        tool_results: list[dict],
    ) -> str:
        evidence = "No tool results."
        if tool_results:
            chunks = []
            for i, result in enumerate(tool_results, start=1):
                chunks.append(
                    f"Tool result {i}: {result['tool']} | ok={result['ok']} | input={result['input']}\n"
                    f"{result['output']}"
                )
            evidence = "\n\n".join(chunks)

        system = f"""You are CrewDev General Chat Agent Mode.

Identity and boundaries:
- You are in normal chat agent mode, not project mode.
- You may plan, reason, research, and synthesize.
- You cannot read/write project files, run bash, mutate git, or create projects from this chat.
- Do not invent tool results. Use the provided tool evidence only.
- If evidence is missing or a tool failed, say what is uncertain and still answer with best effort.
- Be direct, practical, and implementation-oriented.

Web tools enabled: {web_enabled}

Saved chat memory:
{memory_block}

Agent plan:
{json.dumps(plan, ensure_ascii=False)[:2500]}

Tool evidence:
{evidence}
"""
        if skills_block:
            system = f"{skills_block}\n\n{system}"
        return system
