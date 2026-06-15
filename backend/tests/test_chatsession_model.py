import uuid
from sqlalchemy import select
from db.models import ChatSession, Project


async def test_chat_session_has_model_fields(db_session):
    proj = Project(id=str(uuid.uuid4()), name="p", workspace_path="/tmp/p")
    db_session.add(proj)
    await db_session.commit()
    sess = ChatSession(id=str(uuid.uuid4()), project_id=proj.id, title="s",
                       model="gpt-4o", model_provider_id="pid-1")
    db_session.add(sess)
    await db_session.commit()
    got = (await db_session.execute(select(ChatSession))).scalar_one()
    assert got.model == "gpt-4o"
    assert got.model_provider_id == "pid-1"
