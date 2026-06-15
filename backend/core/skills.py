import json

from sqlalchemy import select

from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall
from db.models import Skill

_router = LLMRouter()


async def _enabled_skills(db):
    res = await db.execute(select(Skill).where(Skill.enabled == True))  # noqa: E712
    return list(res.scalars().all())


async def select_skills(db, user_message: str, resolved: ResolvedCall) -> list:
    skills = await _enabled_skills(db)
    if not skills:
        return []  # no skills → no LLM call
    catalog = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    prompt = f"""You route a user message to relevant skills.

AVAILABLE SKILLS:
{catalog}

USER MESSAGE:
{user_message}

Return JSON only: {{"skills": ["<name>", ...]}} listing the names of skills that clearly apply.
Return an empty list if none clearly apply."""
    try:
        text, _ = await _router.acomplete(
            [{"role": "user", "content": prompt}], resolved,
            max_tokens=200, response_format={"type": "json_object"},
        )
        names = set(json.loads(text).get("skills", []))
    except Exception:
        return []
    return [s for s in skills if s.name in names]


def build_skills_block(skills: list) -> str:
    if not skills:
        return ""
    parts = ["ACTIVE SKILLS — follow these instructions when relevant:\n"]
    for s in skills:
        parts.append(f"## {s.name}\n{s.instructions}\n")
    return "\n".join(parts)
