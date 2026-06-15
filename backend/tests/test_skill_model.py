import uuid
from sqlalchemy import select
from db.models import Skill


async def test_skill_persists(db_session):
    s = Skill(id=str(uuid.uuid4()), name="Reviewer", description="reviews code", instructions="List issues by severity.")
    db_session.add(s)
    await db_session.commit()
    got = (await db_session.execute(select(Skill))).scalar_one()
    assert got.name == "Reviewer"
    assert got.enabled is True
    assert got.instructions == "List issues by severity."
