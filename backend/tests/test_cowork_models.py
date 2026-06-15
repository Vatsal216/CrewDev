import uuid
from sqlalchemy import select
from db.models import CoworkSession, CoworkMessage


async def test_cowork_session_and_message(db_session):
    s = CoworkSession(id=str(uuid.uuid4()), title="WS", doc_content="# Hi")
    db_session.add(s)
    await db_session.commit()
    m = CoworkMessage(id=str(uuid.uuid4()), session_id=s.id, role="user", content="hello")
    db_session.add(m)
    await db_session.commit()
    got = (await db_session.execute(select(CoworkSession))).scalar_one()
    assert got.doc_content == "# Hi"
    msgs = (await db_session.execute(select(CoworkMessage))).scalars().all()
    assert len(msgs) == 1 and msgs[0].content == "hello"
