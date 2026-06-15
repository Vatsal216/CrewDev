import json
import uuid
from typing import Optional
from db.models import HarnessState, AsyncSessionLocal
from sqlalchemy import select

from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall

_router = LLMRouter()


class ProjectHarness:
    """
    Persistent awareness layer. Tracks goals, architecture,
    decisions, and ongoing work across sessions.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._state: Optional[dict] = None

    async def _load(self) -> dict:
        if self._state:
            return self._state
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(HarnessState).where(HarnessState.project_id == self.project_id)
            )
            row = result.scalar_one_or_none()
            if row:
                self._state = {
                    "goals": row.goals or [],
                    "architecture": row.architecture or "",
                    "decisions": row.decisions or [],
                    "active_tasks": row.active_tasks or [],
                    "tech_stack": row.tech_stack or {},
                    "summary": row.summary or "",
                }
            else:
                self._state = {
                    "goals": [],
                    "architecture": "",
                    "decisions": [],
                    "active_tasks": [],
                    "tech_stack": {},
                    "summary": "New project — no context yet.",
                }
        return self._state

    async def get_context(self) -> str:
        state = await self._load()
        parts = []
        if state["summary"]:
            parts.append(f"PROJECT SUMMARY:\n{state['summary']}")
        if state["goals"]:
            parts.append(f"GOALS:\n" + "\n".join(f"- {g}" for g in state["goals"]))
        if state["architecture"]:
            parts.append(f"ARCHITECTURE:\n{state['architecture']}")
        if state["tech_stack"]:
            stack_str = ", ".join(f"{k}: {v}" for k, v in state["tech_stack"].items())
            parts.append(f"TECH STACK: {stack_str}")
        if state["decisions"]:
            recent = state["decisions"][-5:]
            parts.append("RECENT DECISIONS:\n" + "\n".join(f"- {d}" for d in recent))
        if state["active_tasks"]:
            parts.append("ACTIVE TASKS:\n" + "\n".join(f"- {t}" for t in state["active_tasks"]))
        return "\n\n".join(parts) if parts else "No project context yet."

    async def update(self, assistant_response: str, resolved: ResolvedCall = None):
        """Extract and persist project intelligence from conversation."""
        state = await self._load()

        prompt = f"""Analyze this assistant response and extract structured project intelligence.
Return JSON only, no markdown.

CURRENT STATE:
{json.dumps(state, indent=2)}

ASSISTANT RESPONSE:
{assistant_response[:3000]}

Return a JSON object with these optional keys (only include if there's new info):
- goals: list of project goals (strings)
- architecture: string describing architecture
- tech_stack: dict of technology -> version/description
- decisions: list of architectural/design decisions made
- active_tasks: list of ongoing/pending tasks
- summary: 2-3 sentence project summary

Only return the JSON object, no other text."""

        try:
            text, _usage = await _router.acomplete(
                [{"role": "user", "content": prompt}],
                resolved,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )
            updates = json.loads(text)

            # Merge updates
            for key in ["goals", "decisions", "active_tasks"]:
                if key in updates:
                    existing = set(state.get(key, []))
                    for item in updates[key]:
                        existing.add(item)
                    state[key] = list(existing)[-20:]  # cap at 20

            for key in ["architecture", "summary"]:
                if key in updates and updates[key]:
                    state[key] = updates[key]

            if "tech_stack" in updates:
                state["tech_stack"].update(updates["tech_stack"])

            self._state = state
            await self._save()
        except Exception:
            pass  # harness update is non-critical

    async def _save(self):
        state = self._state
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(HarnessState).where(HarnessState.project_id == self.project_id)
            )
            row = result.scalar_one_or_none()
            if row:
                row.goals = state["goals"]
                row.architecture = state["architecture"]
                row.decisions = state["decisions"]
                row.active_tasks = state["active_tasks"]
                row.tech_stack = state["tech_stack"]
                row.summary = state["summary"]
            else:
                db.add(HarnessState(
                    id=str(uuid.uuid4()),
                    project_id=self.project_id,
                    **state
                ))
            await db.commit()

    async def set_goal(self, goal: str):
        state = await self._load()
        if goal not in state["goals"]:
            state["goals"].append(goal)
        await self._save()

    async def add_decision(self, decision: str):
        state = await self._load()
        state["decisions"].append(decision)
        state["decisions"] = state["decisions"][-30:]
        await self._save()
