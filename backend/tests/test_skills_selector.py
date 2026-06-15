import uuid
import litellm
from core.skills import select_skills, build_skills_block
from core.llm.types import ResolvedCall
from db.models import Skill

RC = ResolvedCall(model="openai/gpt-4o", kwargs={"api_key": "k"})


class _Msg:
    def __init__(self, c): self.content = c
class _Choice:
    def __init__(self, c): self.message = _Msg(c)
class _Resp:
    def __init__(self, c): self.choices = [_Choice(c)]; self.usage = None


async def test_no_skills_skips_llm_call(monkeypatch, db_session):
    called = {"n": 0}
    async def boom(**kw):
        called["n"] += 1
        raise AssertionError("should not be called")
    monkeypatch.setattr(litellm, "acompletion", boom)
    out = await select_skills(db_session, "anything", RC)
    assert out == []
    assert called["n"] == 0


async def test_selects_matching_skill(monkeypatch, db_session):
    s = Skill(id=str(uuid.uuid4()), name="Reviewer", description="reviews code", instructions="Be strict.")
    db_session.add(s); await db_session.commit()

    async def fake(**kw):
        return _Resp('{"skills": ["Reviewer"]}')
    monkeypatch.setattr(litellm, "acompletion", fake)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)

    out = await select_skills(db_session, "review this", RC)
    assert len(out) == 1 and out[0].name == "Reviewer"


async def test_malformed_selector_returns_empty(monkeypatch, db_session):
    s = Skill(id=str(uuid.uuid4()), name="X", description="d", instructions="i")
    db_session.add(s); await db_session.commit()
    async def fake(**kw):
        return _Resp("not json")
    monkeypatch.setattr(litellm, "acompletion", fake)
    monkeypatch.setattr(litellm, "completion_cost", lambda **kw: 0.0)
    assert await select_skills(db_session, "hi", RC) == []


def test_build_skills_block():
    assert build_skills_block([]) == ""
    s = Skill(id="1", name="Reviewer", description="d", instructions="Be strict.")
    block = build_skills_block([s])
    assert "Reviewer" in block and "Be strict." in block
