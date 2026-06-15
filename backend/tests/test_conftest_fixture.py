import uuid
from sqlalchemy import select
from db.models import GeneralChatSession


async def test_db_session_fixture_round_trips(db_session):
    chat = GeneralChatSession(id=str(uuid.uuid4()), title="hi")
    db_session.add(chat)
    await db_session.commit()
    rows = (await db_session.execute(select(GeneralChatSession))).scalars().all()
    assert len(rows) == 1
    assert rows[0].title == "hi"


def test_anthropic_key_is_optional():
    from config import Settings
    s = Settings()  # must not raise even with ANTHROPIC_API_KEY unset/empty
    assert s.anthropic_api_key == ""
    assert hasattr(s, "openai_api_key")
    assert hasattr(s, "ollama_base_url")
    assert hasattr(s, "ollama_api_key")
